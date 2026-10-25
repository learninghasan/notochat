"""Resource-limited local parsing; input is never executed or fetched by a parser."""
import json,subprocess,sys,tempfile
from pathlib import Path
from fastapi import HTTPException

def extract(raw,mime,kind):
    if kind not in ('document','video','image') or len(raw)>8_000_000:raise HTTPException(422,'Unsupported or oversized media')
    with tempfile.TemporaryDirectory(prefix='notochat-media-') as temporary:
        root=Path(temporary);source=root/'input';source.write_bytes(raw)
        try:
            subprocess.run([sys.executable,'-I',str(Path(__file__).with_name('media_extract_worker.py')),kind,mime,str(source),str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=35,check=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            result=json.loads((root/'result.json').read_text())
            if kind=='video':result['images']=[(root/f'frame-{i}.jpg').read_bytes() for i in range(3)]
            return result
        except (subprocess.SubprocessError,OSError,ValueError):raise HTTPException(422,'Document/video could not be parsed within limits. Use selectable PDF/text, or a supported video under 60 seconds and 1080p.')
