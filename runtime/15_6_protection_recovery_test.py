import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5
from runtime.autonomous_supervisor import AutonomousSupervisor

def main():
    print('=== 15/6 PROTECTION RECOVERY & FAILURE HANDLING ===')
    s=AutonomousSupervisor()
    assert s.connect_stack(), 'INITIAL MT5 CONNECTION FAILED'
    account=s.execution.get_account_info(); print('ACCOUNT:',account)
    assert account.get('status')=='OK' and account.get('trade_allowed') and account.get('trade_expert')
    positions=s.execution.get_open_positions(); print('OPEN POSITIONS:',positions)
    assert s.verify_invariants(positions)
    s.cache_verified_protection(positions)
    assert s.protection_cycle(positions)
    for p in positions:
        assert float(p['sl'])>0 and float(p['tp'])>0
        assert s.protection_is_valid(p), f'INVALID LIVE PROTECTION: {p}'
    assert s.connection_is_healthy()
    print('RESULT: 15/6 PROTECTION RECOVERY PASS')
    print('NO ORDER SENT'); print('NO POSITION MODIFIED'); print('NO POSITION CLOSED')
    s.execution.disconnect(); s.market.disconnect(); mt5.shutdown()
if __name__=='__main__': main()


