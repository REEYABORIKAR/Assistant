import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.resolve()
src_dir = backend_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.chdir(backend_dir)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("refyne.main:app", host="127.0.0.1", port=8000, reload=False)


