$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force .\runtime, .\runtime\signals, .\runtime\logs, .\runtime\reports, .\runtime\state | Out-Null
Copy-Item .\runtime_package\runtime\* .\runtime\ -Recurse -Force
Copy-Item .\runtime_package\run_autonomous.py .\run_autonomous.py -Force
python -m py_compile .\runtime\autonomous_supervisor.py
python -m py_compile .\runtime\15_6_protection_recovery_test.py
python -m py_compile .\run_autonomous.py
Write-Host 'AUTONOMOUS RUNTIME INSTALLATION: PASS' -ForegroundColor Green
