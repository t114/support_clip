from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import shutil
import json
import uuid
import logging
from .paths import PREFIX_IMAGES_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/styles", tags=["styles"])

class ExportStylesRequest(BaseModel):
    styles: dict
    defaultStyleName: str = None
    recentStyleNames: list = None

@router.post("/export")
async def export_styles(request: ExportStylesRequest):
    import zipfile
    import tempfile
    
    try:
        temp_dir = tempfile.mkdtemp()
        
        styles_path = os.path.join(temp_dir, "styles.json")
        with open(styles_path, "w", encoding="utf-8") as f:
            json.dump({
                "styles": request.styles,
                "defaultStyleName": request.defaultStyleName,
                "recentStyleNames": request.recentStyleNames
            }, f, indent=2, ensure_ascii=False)
            
        zip_path = os.path.join(tempfile.gettempdir(), "styles_export.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(styles_path, "styles.json")
            if os.path.exists(PREFIX_IMAGES_DIR):
                for file in os.listdir(PREFIX_IMAGES_DIR):
                    file_path = os.path.join(PREFIX_IMAGES_DIR, file)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, os.path.join("prefix_images", file))
                        
        return FileResponse(
            path=zip_path,
            filename="styles_export.zip",
            media_type="application/zip",
            background=None
        )
    except Exception as e:
        logger.error(f"Error exporting styles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_styles(file: UploadFile = File(...)):
    import zipfile
    import tempfile
    
    try:
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Must be a ZIP file")
            
        zip_path = os.path.join(tempfile.gettempdir(), "styles_import.zip")
        with open(zip_path, "wb") as f:
            f.write(await file.read())
            
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)
            
        extracted_prefix = os.path.join(temp_dir, "prefix_images")
        if os.path.exists(extracted_prefix):
            os.makedirs(PREFIX_IMAGES_DIR, exist_ok=True)
            for item in os.listdir(extracted_prefix):
                src = os.path.join(extracted_prefix, item)
                dst = os.path.join(PREFIX_IMAGES_DIR, item)
                shutil.copy2(src, dst)
                
        styles_file = os.path.join(temp_dir, "styles.json")
        styles_data = {}
        if os.path.exists(styles_file):
            with open(styles_file, "r", encoding="utf-8") as f:
                styles_data = json.load(f)
                
        return {"status": "success", "data": styles_data}
    except Exception as e:
        logger.error(f"Error importing styles: {e}")
        raise HTTPException(status_code=500, detail=str(e))
