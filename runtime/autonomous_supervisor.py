from __future__ import annotations
import json, logging, signal, time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
import MetaTrader5 as mt5
from market.market_data import MarketData
from risk.risk_manager import RiskManager
from execution.mt5_execution import MT5ExecutionEngine

UTC = timezone.utc

@dataclass
class SupervisorConfig:
    runtime_days: float = 7.0
    poll_seconds: float = 5.0
    reconnect_seconds: float = 5.0
    report_interval_seconds: float = 300.0
    signal_file: str = 'runtime/signals/next_signal.json'
    log_dir: str = 'runtime/logs'
    state_file: str = 'runtime/state/supervisor_state.json'
    report_dir: str = 'runtime/reports'
    recovery_attempts: int = 3

class AutonomousSupervisor:
    ENGINE_NAME = 'SUPPLY & DEMAND AUTONOMOUS SUPERVISOR'
    VERSION = '1.0.0'
    def __init__(self, config: Optional[SupervisorConfig]=None):
        self.cfg=config or SupervisorConfig(); self.started_at=None; self.stop_requested=False
        self.halted=False; self.halt_reason=None; self.market=None; self.risk=None; self.execution=None
        self.account_identity={}; self.protection_cache={}; self.last_report_at=None; self.last_signal_fingerprint=None
        self.stats={'cycles':0,'connection_failures':0,'reconnections':0,'protection_checks':0,'protection_repairs':0,'entries_attempted':0,'entries_executed':0,'entries_blocked':0,'critical_halts':0,'events':0}
        for p in (Path(self.cfg.log_dir),Path(self.cfg.report_dir),Path(self.cfg.state_file).parent,Path(self.cfg.signal_file).parent): p.mkdir(parents=True,exist_ok=True)
        self.logger=logging.getLogger('supply_demand_autonomous'); self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            fh=logging.FileHandler(Path(self.cfg.log_dir)/'autonomous_supervisor.log',encoding='utf-8'); fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')); self.logger.addHandler(fh)
            ch=logging.StreamHandler(); ch.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')); self.logger.addHandler(ch)
        signal.signal(signal.SIGINT,self._signal_stop)
        if hasattr(signal,'SIGTERM'): signal.signal(signal.SIGTERM,self._signal_stop)
    def _signal_stop(self,signum,_frame): self.logger.warning('STOP REQUEST RECEIVED: %s',signum); self.stop_requested=True
    def _event(self,event,**payload):
        self.stats['events']+=1; self.logger.info(json.dumps({'timestamp':datetime.now(UTC).isoformat(),'event':event,**payload},default=str,sort_keys=True)); self._save_state()
    def _save_state(self):
        Path(self.cfg.state_file).write_text(json.dumps({'engine':self.ENGINE_NAME,'version':self.VERSION,'started_at':self.started_at.isoformat() if self.started_at else None,'halted':self.halted,'halt_reason':self.halt_reason,'account_identity':self.account_identity,'protection_cache':self.protection_cache,'stats':self.stats,'saved_at':datetime.now(UTC).isoformat()},indent=2,default=str),encoding='utf-8')
    def connect_stack(self):
        self.market=MarketData()
        if not self.market.connect(): self._event('CONNECTION_FAILED',component='MarketData'); return False
        self.risk=RiskManager(self.market); self.execution=MT5ExecutionEngine(self.risk)
        if not self.execution.connect(): self._event('CONNECTION_FAILED',component='MT5ExecutionEngine'); self.market.disconnect(); return False
        account=self.execution.get_account_info()
        if account.get('status')!='OK': self._event('ACCOUNT_READ_FAILED',account=account); return False
        self.account_identity={k:account.get(k) for k in ('login','server','company','currency')}
        self._event('CONNECTED',account=self.account_identity,execution_enabled=self.execution.EXECUTION_ENABLED,simulation_enabled=self.execution.SIMULATION_ENABLED); return True
    def connection_is_healthy(self):
        try:
            if self.execution is None or not self.execution.is_connected(): return False
            terminal,account=mt5.terminal_info(),mt5.account_info()
            if terminal is None or account is None or not bool(getattr(terminal,'connected',False)): return False
            identity={k:getattr(account,k,None) for k in ('login','server','company','currency')}
            if identity!=self.account_identity: self.halt('ACCOUNT_IDENTITY_CHANGED',previous=self.account_identity,current=identity); return False
            return True
        except Exception as exc: self._event('CONNECTION_CHECK_EXCEPTION',error=str(exc)); return False
    def recover_connection(self):
        self.stats['connection_failures']+=1; self._event('CONNECTION_RECOVERY_START')
        for attempt in range(1,self.cfg.recovery_attempts+1):
            try:
                if self.execution: self.execution.disconnect()
                if self.market: self.market.disconnect()
            except Exception: pass
            time.sleep(self.cfg.reconnect_seconds)
            if self.connect_stack(): self.stats['reconnections']+=1; self._event('CONNECTION_RECOVERED',attempt=attempt); return True
            self._event('CONNECTION_RECOVERY_ATTEMPT_FAILED',attempt=attempt)
        self.halt('MT5_CONNECTION_RECOVERY_FAILED'); return False
    def snapshot_positions(self): return self.execution.get_open_positions()
    def cache_verified_protection(self,positions):
        for p in positions:
            sl,tp=float(p.get('sl',0)),float(p.get('tp',0))
            if sl>0 and tp>0: self.protection_cache[str(int(p['ticket']))]={'ticket':int(p['ticket']),'symbol':p['symbol'],'volume':float(p['volume']),'type':int(p['type']),'sl':sl,'tp':tp,'cached_at':datetime.now(UTC).isoformat()}
            else: self._event('UNPROTECTED_POSITION_DETECTED',ticket=p['ticket'],symbol=p['symbol'],sl=sl,tp=tp)
    def protection_is_valid(self,p):
        sl,tp=float(p.get('sl',0)),float(p.get('tp',0));
        if sl<=0 or tp<=0: return False
        tick=self.execution.get_current_tick(p['symbol'])
        if tick.get('status')!='OK': return False
        bid,ask=float(tick['bid']),float(tick['ask'])
        return (sl<bid and tp>bid) if int(p['type'])==mt5.POSITION_TYPE_BUY else (sl>ask and tp<ask)
    def recover_position_protection(self,p):
        ticket=int(p['ticket']); cache=self.protection_cache.get(str(ticket))
        if not cache: self.halt('PROTECTION_RECOVERY_UNSAFE_NO_SNAPSHOT',ticket=ticket,symbol=p['symbol']); return False
        if cache['symbol']!=p['symbol'] or abs(cache['volume']-float(p['volume']))>1e-9: self.halt('PROTECTION_RECOVERY_POSITION_IDENTITY_MISMATCH',ticket=ticket); return False
        sl,tp=cache['sl'],cache['tp']; tick=self.execution.get_current_tick(p['symbol'])
        if tick.get('status')!='OK': self.halt('PROTECTION_RECOVERY_NO_LIVE_TICK',ticket=ticket); return False
        bid,ask=float(tick['bid']),float(tick['ask'])
        safe=(sl<bid and tp>bid) if int(p['type'])==mt5.POSITION_TYPE_BUY else (sl>ask and tp<ask)
        if not safe: self.halt('PROTECTION_SNAPSHOT_NOW_UNSAFE',ticket=ticket); return False
        result=self.execution.modify_position_protection(ticket,sl,tp)
        if result.get('status')!='PROTECTION_UPDATED': self.halt('PROTECTION_RECOVERY_FAILED',ticket=ticket,result=result); return False
        self.stats['protection_repairs']+=1; self._event('PROTECTION_RECOVERED',ticket=ticket,symbol=p['symbol'],sl=sl,tp=tp,result=result); return True
    def protection_cycle(self,positions):
        self.stats['protection_checks']+=1; self.cache_verified_protection(positions)
        for p in positions:
            if not self.protection_is_valid(p):
                self._event('PROTECTION_INVALID',ticket=p['ticket'],symbol=p['symbol'],sl=p.get('sl'),tp=p.get('tp'))
                if not self.recover_position_protection(p): return False
        return True
    def load_signal(self):
        path=Path(self.cfg.signal_file)
        if not path.exists(): return None
        try:
            data=json.loads(path.read_text(encoding='utf-8')); return data if isinstance(data,dict) else None
        except Exception as exc: self._event('SIGNAL_READ_FAILED',error=str(exc)); return None
    def execute_external_signal_if_allowed(self,positions):
        data=self.load_signal()
        if not data: return
        fp=json.dumps(data,sort_keys=True,default=str)
        if fp==self.last_signal_fingerprint: return
        self.last_signal_fingerprint=fp; self._event('SIGNAL_RECEIVED',signal=data)
        decision=str(data.get('decision','')).upper()
        if decision in ('','NO_TRADE','HOLD'): self._event('SIGNAL_REJECTED',reason='NO_ACTION_DECISION'); return
        if decision not in ('BUY','SELL'): self._event('SIGNAL_REJECTED',reason='INVALID_DECISION',decision=decision); return
        if positions: self.stats['entries_blocked']+=1; self._event('ENTRY_BLOCKED',reason='OPEN_POSITION_EXISTS'); return
        symbol=str(data.get('symbol','')).strip(); volume=float(data.get('volume',0)); sl=float(data.get('stop_loss',0)); tp=float(data.get('take_profit',0))
        if not symbol or volume<=0 or sl<=0 or tp<=0: self.stats['entries_blocked']+=1; self._event('ENTRY_BLOCKED',reason='INCOMPLETE_SIGNAL'); return
        tick=self.execution.get_current_tick(symbol)
        if tick.get('status')!='OK': self.stats['entries_blocked']+=1; self._event('ENTRY_BLOCKED',reason='LIVE_TICK_UNAVAILABLE'); return
        entry=float(tick['ask'] if decision=='BUY' else tick['bid'])
        risk=self.risk.validate_trade(symbol,decision,entry,sl,tp,volume); self._event('RISK_GATE_RESULT',result=risk)
        if not risk.get('approved'): self.stats['entries_blocked']+=1; return
        self.stats['entries_attempted']+=1
        result=self.execution.execute(symbol=symbol,side=decision,volume=volume,stop_loss=sl,take_profit=tp,forecast={'decision':decision,'symbol':symbol})
        self._event('EXECUTION_RESULT',result=result)
        if result.get('status')=='ORDER_EXECUTED': self.stats['entries_executed']+=1
    def verify_invariants(self,positions):
        if self.execution is None: self.halt('EXECUTION_ENGINE_MISSING'); return False
        if not self.execution.EXECUTION_ENABLED: self.halt('EXECUTION_DISABLED'); return False
        if self.execution.SIMULATION_ENABLED: self.halt('SIMULATION_MODE_FORBIDDEN'); return False
        if len(positions)>self.execution.MAX_OPEN_TRADES: self.halt('MAX_OPEN_POSITION_INVARIANT_VIOLATION',count=len(positions)); return False
        for p in positions:
            if float(p.get('volume',0))<=0: self.halt('INVALID_POSITION_VOLUME',ticket=p.get('ticket')); return False
        return True
    def halt(self,reason,**payload):
        if self.halted:return
        self.halted=True; self.halt_reason=reason; self.stats['critical_halts']+=1; self._event('CRITICAL_HALT',reason=reason,**payload)
    def write_report(self,final=False):
        if not self.started_at:return
        now=datetime.now(UTC); account=self.execution.get_account_info() if self.execution else {}; positions=self.execution.get_open_positions() if self.execution else []
        report={'engine':self.ENGINE_NAME,'version':self.VERSION,'generated_at':now.isoformat(),'final':final,'started_at':self.started_at.isoformat(),'planned_end_at':(self.started_at+timedelta(days=self.cfg.runtime_days)).isoformat(),'halted':self.halted,'halt_reason':self.halt_reason,'account_identity':self.account_identity,'account':account,'open_positions':positions,'protection_cache':self.protection_cache,'stats':self.stats}
        Path(self.cfg.report_dir,f"runtime_{now:%Y%m%d_%H%M%S}{'_FINAL' if final else ''}.json").write_text(json.dumps(report,indent=2,default=str),encoding='utf-8'); self.last_report_at=time.time()
    def cycle(self):
        self.stats['cycles']+=1
        if not self.connection_is_healthy(): self.recover_connection(); return
        positions=self.snapshot_positions()
        if not self.verify_invariants(positions): return
        if not self.protection_cycle(positions): return
        positions=self.snapshot_positions()
        if not self.verify_invariants(positions): return
        self.execute_external_signal_if_allowed(positions)
        if self.last_report_at is None or time.time()-self.last_report_at>=self.cfg.report_interval_seconds:self.write_report(False)
        self._save_state()
    def run(self):
        self.started_at=datetime.now(UTC); self._event('SUPERVISOR_START',runtime_days=self.cfg.runtime_days,poll_seconds=self.cfg.poll_seconds)
        if not self.connect_stack(): self.halt('INITIAL_CONNECTION_FAILED'); self.write_report(True); return 2
        positions=self.snapshot_positions(); self.cache_verified_protection(positions)
        if not self.verify_invariants(positions): self.write_report(True); return 3
        if not self.protection_cycle(positions): self.write_report(True); return 4
        deadline=self.started_at+timedelta(days=self.cfg.runtime_days)
        try:
            cycle_number = 0
            while not self.stop_requested and not self.halted and datetime.now(UTC)<deadline:
                cycle_number += 1
                cycle_started = datetime.now(UTC)

                try:
                    self.cycle()

                    positions = self.snapshot_positions()
                    account = self.execution.get_account_info() if self.execution else {}

                    self._event(
                        'HEARTBEAT',
                        cycle=cycle_number,
                        connected=bool(
                            getattr(self.execution, 'connected', False)
                        ),
                        execution_enabled=bool(
                            getattr(self.execution, 'EXECUTION_ENABLED', False)
                        ),
                        simulation_enabled=bool(
                            getattr(self.execution, 'SIMULATION_ENABLED', False)
                        ),
                        open_positions=len(positions),
                        trades_today=(
                            self.execution.get_trades_today_count()
                            if self.execution
                            else None
                        ),
                        account_status=(
                            account.get('status')
                            if isinstance(account, dict)
                            else None
                        ),
                        trade_allowed=(
                            account.get('trade_allowed')
                            if isinstance(account, dict)
                            else None
                        ),
                        trade_expert=(
                            account.get('trade_expert')
                            if isinstance(account, dict)
                            else None
                        ),
                        halted=self.halted,
                        cycle_timestamp=cycle_started.isoformat(),
                    )

                except Exception as exc:
                    self._event(
                        'CYCLE_EXCEPTION',
                        cycle=cycle_number,
                        error=str(exc),
                        halted=self.halted,
                    )
                    self.halt(
                        'UNHANDLED_RUNTIME_EXCEPTION',
                        error=str(exc),
                    )
                    break

                if not self.stop_requested and not self.halted:
                    time.sleep(self.cfg.poll_seconds)
            if datetime.now(UTC)>=deadline:self._event('RUNTIME_DURATION_REACHED')
        finally:
            self.write_report(True)
            try:
                if self.execution:self.execution.disconnect()
            finally:
                if self.market:self.market.disconnect()
            self._event('SUPERVISOR_STOP',halted=self.halted,halt_reason=self.halt_reason)
        return 1 if self.halted else 0

def main(): return AutonomousSupervisor().run()
if __name__=='__main__': raise SystemExit(main())
