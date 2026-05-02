from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Optional
import os
import shutil
import json
import logging
import datetime

from .paths import EMOJIS_DIR
from .chat_utils import (
    get_channel_info, 
    refresh_channels_summary_cache, 
    refresh_common_emojis_cache
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emojis", tags=["emojis"])
youtube_sync_router = APIRouter(prefix="/youtube", tags=["youtube-emojis"])

class SyncEmojiRequest(BaseModel):
    channel_id: str
    channel_name: Optional[str] = None
    emojis: Dict[str, str] # shortcut -> url

class EmojiConfigsRequest(BaseModel):
    configs: dict

@youtube_sync_router.post("/sync-emojis")
async def sync_emojis(request: SyncEmojiRequest):
    try:
        import requests
        channel_id = request.channel_id
        if not channel_id or channel_id == "UNKNOWN_CHANNEL":
             raise HTTPException(status_code=400, detail="Channel ID is required")
             
        channel_dir = os.path.join(EMOJIS_DIR, channel_id)
        if os.path.exists(channel_dir):
            shutil.rmtree(channel_dir)
            
        os.makedirs(channel_dir, exist_ok=True)
        saved_count = 0
        local_mapping = {}
        mapping_file = os.path.join(channel_dir, "map.json")
        
        for shortcut, url in request.emojis.items():
            safe_name = "".join([c for c in shortcut if c.isalnum() or c in "_-"]).strip("_")
            if not safe_name: safe_name = f"emoji_{hash(shortcut)}"
            
            ext = ".png"
            if ".webp" in url: ext = ".webp"
            elif ".gif" in url: ext = ".gif"
            
            filename = f"{safe_name}{ext}"
            file_path = os.path.join(channel_dir, filename)
            local_mapping[shortcut] = filename
            
            if not os.path.exists(file_path):
                try:
                    resp = requests.get(url, stream=True, timeout=10)
                    if resp.status_code == 200:
                        with open(file_path, 'wb') as f:
                            for chunk in resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        saved_count += 1
                except Exception as e:
                     logger.warning(f"Failed to download emoji {shortcut}: {e}")
            else:
                saved_count += 1
                
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(local_mapping, f, ensure_ascii=False, indent=2)

        if request.channel_name:
            info_file = os.path.join(channel_dir, "channel_info.json")
            info_data = {"name": request.channel_name, "registered_at": datetime.datetime.now().isoformat()}
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(info_data, f, ensure_ascii=False, indent=2)

        refresh_channels_summary_cache()
        return {"status": "success", "saved_count": saved_count, "channel_id": channel_id}
    except Exception as e:
        logger.error(f"Error syncing emojis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
async def get_emoji_list():
    summary_path = os.path.join(EMOJIS_DIR, "summary.json")
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding='utf-8') as f:
                data = json.load(f)
                return {"channels": data.get("channels", [])}
        except: pass
    
    channels = refresh_channels_summary_cache()
    return {"channels": channels}

@router.get("/common")
async def get_common_emojis():
    cache_path = os.path.join(EMOJIS_DIR, "common_emojis.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding='utf-8') as f:
                data = json.load(f)
                return {"common": data.get("common", [])}
        except: pass
    
    common = refresh_common_emojis_cache()
    return {"common": common}

@router.get("/export")
async def export_emojis():
    import zipfile
    import tempfile
    try:
        if not os.path.exists(EMOJIS_DIR):
            raise HTTPException(status_code=404, detail="No emojis found")
            
        zip_path = os.path.join(tempfile.gettempdir(), "emojis_export.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(EMOJIS_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, EMOJIS_DIR)
                    zipf.write(file_path, arcname)
                    
        return FileResponse(
            path=zip_path,
            filename="emojis_export.zip",
            media_type="application/zip",
            background=None
        )
    except Exception as e:
        logger.error(f"Error exporting emojis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_emojis(file: UploadFile = File(...)):
    import zipfile
    import tempfile
    try:
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Must be a ZIP file")
            
        zip_path = os.path.join(tempfile.gettempdir(), "emojis_import.zip")
        with open(zip_path, "wb") as f:
            f.write(await file.read())
            
        os.makedirs(EMOJIS_DIR, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(EMOJIS_DIR)
            
        refresh_common_emojis_cache()
        refresh_channels_summary_cache()
        
        return {"status": "success", "message": "Emojis imported successfully"}
    except Exception as e:
        logger.error(f"Error importing emojis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{channel_id}")
async def get_emoji_details(channel_id: str):
    channel_dir = os.path.join(EMOJIS_DIR, channel_id)
    if not os.path.exists(channel_dir):
        raise HTTPException(status_code=404, detail="Channel not found")
        
    mapping_file = os.path.join(channel_dir, "map.json")
    if not os.path.exists(mapping_file):
        return {"id": channel_id, "emojis": []}
        
    try:
        with open(mapping_file, "r", encoding='utf-8') as f:
            emojis = json.load(f)
            
        configs_file = os.path.join(channel_dir, "configs.json")
        configs = {}
        if os.path.exists(configs_file):
            try:
                with open(configs_file, "r", encoding='utf-8') as f:
                    configs = json.load(f)
            except: pass
            
        detail_list = []
        for shortcut, filename in emojis.items():
            detail_list.append({
                "shortcut": shortcut,
                "url": f"/static/emojis/{channel_id}/{filename}",
                "categories": configs.get(shortcut, [])
            })
            
        name, registered_at = get_channel_info(channel_id)
        return {
            "id": channel_id,
            "name": name,
            "registered_at": registered_at,
            "emojis": detail_list
        }
    except Exception as e:
        logger.error(f"Error reading emoji details for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{channel_id}/configs")
async def update_emoji_configs(channel_id: str, request: EmojiConfigsRequest):
    try:
        channel_dir = os.path.join(EMOJIS_DIR, channel_id)
        if not os.path.exists(channel_dir):
            raise HTTPException(status_code=404, detail="Channel not found")
            
        configs_file = os.path.join(channel_dir, "configs.json")
        with open(configs_file, "w", encoding='utf-8') as f:
            json.dump(request.configs, f, ensure_ascii=False, indent=2)
            
        refresh_common_emojis_cache()
        refresh_channels_summary_cache()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error updating emoji configs for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{channel_id}")
async def delete_emojis(channel_id: str):
    try:
        channel_dir = os.path.join(EMOJIS_DIR, channel_id)
        if not os.path.exists(channel_dir):
            raise HTTPException(status_code=404, detail="Channel not found")
            
        shutil.rmtree(channel_dir)
        refresh_common_emojis_cache()
        refresh_channels_summary_cache()
        return {"status": "success", "message": f"Deleted emojis for {channel_id}"}
    except Exception as e:
        logger.error(f"Error deleting emojis for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
