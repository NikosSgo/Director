"""Сохранение и загрузка данных проекта."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.api import GatewayClient
from app.components.editor.assets_panel import Asset, AssetType
from app.components.editor.timeline import Clip, Track, TrackType


class ProjectData:
    """Менеджер данных проекта (сохранение/загрузка)."""
    
    PROJECT_FILE = "project.json"
    
    def __init__(self, project_path: str, gateway: Optional[GatewayClient] = None):
        self._project_path = project_path
        self._gateway = gateway
        self._data: Dict[str, Any] = {
            "version": "1.0",
            "assets": [],
            "tracks": [],
            "clips": [],
        }
    
    @property
    def project_file_path(self) -> str:
        return f"{self._project_path}/{self.PROJECT_FILE}"
    
    def load(self) -> bool:
        """Загрузить данные проекта с сервера."""
        if not self._gateway:
            return False
        
        try:
            # Скачиваем project.json
            response = self._gateway.browse_directory(self._project_path)
            if not response.success:
                return False
            
            # Проверяем есть ли project.json
            has_project_file = any(
                e.name == self.PROJECT_FILE 
                for e in response.entries
            )
            
            if not has_project_file:
                # Создаём пустой файл проекта
                self.save()
                return True
            
            # Читаем файл (скачиваем локально)
            import tempfile
            import os
            
            temp_file = tempfile.mktemp(suffix=".json")
            try:
                self._gateway.download_file(
                    self.project_file_path,
                    temp_file
                )
                
                with open(temp_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                
                return True
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
        except Exception as e:
            print(f"[ProjectData] Load error: {e}")
            return False
    
    def save(self) -> bool:
        """Сохранить данные проекта на сервер."""
        if not self._gateway:
            return False
        
        try:
            import tempfile
            import os
            
            # Записываем во временный файл
            temp_file = tempfile.mktemp(suffix=".json")
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                
                # Загружаем на сервер
                response = self._gateway.upload_file(
                    local_path=temp_file,
                    destination_path=self._project_path,
                    filename=self.PROJECT_FILE,
                    overwrite=True,
                )
                
                return response.success
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
        except Exception as e:
            print(f"[ProjectData] Save error: {e}")
            return False
    
    # === Assets ===
    
    def get_assets(self) -> List[Asset]:
        """Получить список ассетов."""
        assets = []
        for data in self._data.get("assets", []):
            try:
                assets.append(Asset(
                    id=data["id"],
                    name=data["name"],
                    file_path=data["file_path"],
                    local_path=data.get("local_path", ""),
                    asset_type=AssetType[data["asset_type"]],
                    duration_ms=data.get("duration_ms", 0),
                    width=data.get("width", 0),
                    height=data.get("height", 0),
                    size_bytes=data.get("size_bytes", 0),
                ))
            except (KeyError, ValueError) as e:
                print(f"[ProjectData] Asset parse error: {e}")
        return assets
    
    def set_assets(self, assets: List[Asset]) -> None:
        """Установить список ассетов."""
        self._data["assets"] = [
            {
                "id": a.id,
                "name": a.name,
                "file_path": a.file_path,
                "local_path": a.local_path,
                "asset_type": a.asset_type.name,
                "duration_ms": a.duration_ms,
                "width": a.width,
                "height": a.height,
                "size_bytes": a.size_bytes,
            }
            for a in assets
        ]
    
    def add_asset(self, asset: Asset) -> None:
        """Добавить ассет."""
        assets = self.get_assets()
        assets.append(asset)
        self.set_assets(assets)
    
    def remove_asset(self, asset_id: str) -> None:
        """Удалить ассет."""
        assets = [a for a in self.get_assets() if a.id != asset_id]
        self.set_assets(assets)
    
    # === Tracks & Clips ===
    
    def get_tracks(self) -> List[Dict]:
        """Получить треки."""
        return self._data.get("tracks", [])
    
    def set_tracks(self, tracks: List[Dict]) -> None:
        """Установить треки."""
        self._data["tracks"] = tracks
    
    def get_clips(self) -> List[Dict]:
        """Получить клипы."""
        return self._data.get("clips", [])
    
    def set_clips(self, clips: List[Dict]) -> None:
        """Установить клипы."""
        self._data["clips"] = clips
    
    def add_clip(self, clip_data: Dict) -> None:
        """Добавить клип."""
        clips = self.get_clips()
        clips.append(clip_data)
        self.set_clips(clips)
    
    def remove_clip(self, clip_id: str) -> None:
        """Удалить клип."""
        clips = [c for c in self.get_clips() if c.get("id") != clip_id]
        self.set_clips(clips)
    
    def update_clip(self, clip_id: str, updates: Dict) -> None:
        """Обновить клип."""
        clips = self.get_clips()
        for clip in clips:
            if clip.get("id") == clip_id:
                clip.update(updates)
                break
        self.set_clips(clips)

