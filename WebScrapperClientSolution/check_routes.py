"""
Diagnostic script to check FastAPI routes
Run this in your project directory: py check_routes.py
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.routes import calendar_router
    
    print("=" * 80)
    print("CALENDAR ROUTER ROUTES")
    print("=" * 80)
    
    routes_found = []
    stop_all_found = False
    
    for route in calendar_router.routes:
        path = route.path
        methods = list(route.methods) if hasattr(route, 'methods') else []
        name = route.name if hasattr(route, 'name') else 'unknown'
        
        routes_found.append(f"{methods[0] if methods else 'GET':<6} {path:<50} {name}")
        
        if 'stop-all' in path or 'stop_all' in name:
            stop_all_found = True
            print(f"✅ FOUND: {methods[0] if methods else 'GET'} {path} ({name})")
    
    print(f"\nTotal routes: {len(routes_found)}")
    print("\nAll routes:")
    for route in routes_found:
        print(f"  {route}")
    
    if not stop_all_found:
        print("\n" + "!" * 80)
        print("❌ WARNING: /webhook/stop-all endpoint NOT FOUND in router!")
        print("!" * 80)
        print("\nThis means your local calendar_routes.py file is missing the endpoint.")
        print("Please check: C:\\Dev\\WebScrapperClientSolution\\app\\routes\\calendar_routes.py")
        print("The endpoint should be around line 495.")
    else:
        print("\n" + "=" * 80)
        print("✅ SUCCESS: /webhook/stop-all endpoint IS registered!")
        print("=" * 80)
        print("\nIf you still don't see it in Swagger, try:")
        print("1. Clear browser cache completely")
        print("2. Try incognito/private mode")
        print("3. Try a different browser")
        print("4. Check http://localhost:8000/openapi.json directly")
    
except Exception as e:
    print(f"❌ Error loading routes: {e}")
    print(f"\nError type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    print("\nMake sure you run this from your project root directory:")
    print("  cd C:\\Dev\\WebScrapperClientSolution")
    print("  py check_routes.py")
