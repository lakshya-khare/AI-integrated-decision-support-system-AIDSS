"""
AIDSS Rail Traffic Controller - Service Launcher
Indian Railways | East Coast Railway (ECoR) | Waltair Division
"""

import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8050))
    print("=" * 75)
    print("   INDIAN RAILWAYS - ADVANCED TRAIN TRAFFIC DECISION SUPPORT SYSTEM (AIDSS)")
    print("   EAST COAST RAILWAY | WALTAIR DIVISION | KTV-PSA CORRIDOR (176.8 KM)")
    print("=" * 75)
    print(f"   Controller Console : http://127.0.0.1:{port}")
    print(f"   OpenAPI REST Docs  : http://127.0.0.1:{port}/docs")
    print("   Operating Mode     : Digital Twin (Ready for Live TMS / COA API)")
    print("=" * 75)
    
    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=port, reload=False)
