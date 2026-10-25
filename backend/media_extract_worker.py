"""Isolated bounded parser process. Input/output paths are created by our parent only."""
import io,json,math,os,resource,subprocess,sys
from pathlib import Path

# Limits apply to this process and its parser subprocesses. No shell is used.
resource.setrlimit(resource.RLIMIT_CPU,(15,15))
resource.setrlimit(resource.RLIMIT_AS,(1024*1024*1024,1024*1024*1024))
resource.setrlimit(resource.RLIMIT_FSIZE,(8_000_000,8_000_000))
resource.setrlimit(resource.RLIMIT_NOFILE,(48,48))
os.umask(0o077)
mode,mime,input_path,output_path=sys.argv[1:]
source=Path(input_path);output=Path(output_path)
if mode=='document':
    raw=source.read_bytes()
    if len(raw)>5_000_000:raise ValueError('Document too large')
    if mime=='application/pdf':
        from pypdf import PdfReader
        if not raw.startswith(b'%PDF-'):raise ValueError('Invalid PDF signature')
        reader=PdfReader(io.BytesIO(raw),strict=True)
        if reader.is_encrypted or len(reader.pages)>50:raise ValueError('Encrypted or long PDF')
        text='\n'.join((page.extract_text() or '')[:10000] for page in reader.pages)[:50000]
    else:
        if len(raw)>100000 or b'\x00' in raw:raise ValueError('Invalid text document')
        text=raw.decode('utf-8-sig')[:50000]
    if not text.strip():raise ValueError('No selectable document text')
    (output/'result.json').write_text(json.dumps({'text':text,'kind':'document','requires_review':True}))
elif mode=='video':
    fmt='mov' if mime=='video/mp4' else 'matroska'
    options=['-protocol_whitelist','file,pipe','-f',fmt]
    if fmt=='mov':options+=['-enable_drefs','0','-use_absolute_path','0']
    probe=output/'probe.json'
    with probe.open('wb') as f:
        subprocess.run(['ffprobe','-v','error',*options,'-show_entries','format=duration:stream=codec_type,codec_name,width,height','-of','json',str(source)],stdout=f,stderr=subprocess.DEVNULL,timeout=10,check=True)
    if probe.stat().st_size>100000:raise ValueError('Excessive metadata')
    data=json.loads(probe.read_text());duration=float(data.get('format',{}).get('duration',0));streams=data.get('streams',[])
    video=[s for s in streams if s.get('codec_type')=='video']
    if not 0<duration<=60 or not math.isfinite(duration) or len(streams)>4 or len(video)!=1:raise ValueError('Use one short video stream')
    v=video[0]
    if v.get('codec_name') not in ('h264','hevc','vp8','vp9','av1') or not 0<v.get('width',0)<=1920 or not 0<v.get('height',0)<=1080:raise ValueError('Unsupported codec or dimensions')
    for i,timestamp in enumerate([0,duration/2,max(0,duration-.2)]):
        target=output/f'frame-{i}.jpg'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-threads','1',*options,'-ss',str(timestamp),'-i',str(source),'-frames:v','1','-an','-sn','-dn','-vf','scale=512:-2','-threads','1','-y',str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=True)
        if not target.exists() or target.stat().st_size>1_000_000:raise ValueError('Frame could not be bounded')
    (output/'result.json').write_text(json.dumps({'duration':duration,'frames':3,'audio_included':False}))
else:raise ValueError('Unknown parser')
