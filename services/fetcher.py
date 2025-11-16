from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import json
from config import logger


class DriveFetcher:
    """Fetches files from Google Drive."""
    def __init__(self, settingsFile: str = "local.settings.json", scopes: list[str] | None = None):
        self.scopes = scopes or ["https://www.googleapis.com/auth/drive.readonly"]
        
        # Load service account credentials from local.settings.json
        with open(settingsFile, 'r') as file:
            settings = json.load(file)
            serviceAccountInfo = settings.get('GoogleServiceAccount')
            
            if not serviceAccountInfo:
                raise ValueError("GoogleServiceAccount not found in settings file")
        
        self.creds = service_account.Credentials.from_service_account_info(
            serviceAccountInfo,
            scopes=self.scopes,
        )
        self.drive = build("drive", "v3", credentials=self.creds)

    def findFolderByName(self, folderName: str, parentId: str | None = None):
        """Find a folder by name, optionally within a parent folder."""
        query = f"name='{folderName}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parentId:
            query += f" and '{parentId}' in parents"
        
        results = self.drive.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=10
        ).execute()
        
        files = results.get('files', [])
        return files[0] if files else None

    def listFilesInFolder(self, folderId: str, mimeType: str | None = None):
        """List all files in a folder, optionally filtered by MIME type."""
        query = f"'{folderId}' in parents and trashed=false"
        if mimeType:
            query += f" and mimeType='{mimeType}'"
        
        results = self.drive.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, modifiedTime)',
            pageSize=100,
            orderBy='modifiedTime desc'
        ).execute()
        
        return results.get('files', [])

    def downloadFile(self, fileId: str, destinationPath: str):
        """Download a file from Google Drive."""
        request = self.drive.files().get_media(fileId=fileId)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(destinationPath) if os.path.dirname(destinationPath) else '.', exist_ok=True)

        with open(destinationPath, "wb") as fileHandle:
            downloader = MediaIoBaseDownload(fileHandle, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Downloaded {status.progress() * 100:.1f}%")

    def fetchLatestExcelFromFolder(self, folderName: str, destinationPath: str | None = None):
        """Find the 'Nhu Tin' folder and download the latest Excel file."""
        logger.info(f"🔍 Looking for folder: {folderName}")
        folder = self.findFolderByName(folderName)
        
        if not folder:
            logger.error(f"❌ Folder '{folderName}' not found")
            return None
        
        logger.info(f"✅ Found folder: {folder['name']} (ID: {folder['id']})")
        
        # Look for Excel files
        excelMimeTypes = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
            'application/vnd.ms-excel',  # .xls
        ]
        
        allExcelFiles = []
        for mimeType in excelMimeTypes:
            files = self.listFilesInFolder(folder['id'], mimeType)
            allExcelFiles.extend(files)
        
        if not allExcelFiles:
            logger.error(f"❌ No Excel files found in '{folderName}'")
            return None
        
        # Sort by modified time (most recent first)
        allExcelFiles.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
        latestFile = allExcelFiles[0]
        
        logger.info(f"📄 Latest Excel file: {latestFile['name']} (modified: {latestFile.get('modifiedTime', 'unknown')})")
        
        # Determine destination path (always under /tmp for Azure Functions)
        baseDir = "/tmp"
        if destinationPath:
            # If caller provides a relative or nested path, place it under /tmp
            # If they accidentally pass an absolute path, strip the leading slash
            # to avoid escaping /tmp.
            cleanedDestinationPath = destinationPath.lstrip(os.sep)
            destinationPath = os.path.join(baseDir, cleanedDestinationPath)
        else:
            destinationPath = os.path.join(baseDir, latestFile['name'])
        
        logger.info(f"⬇️  Downloading to: {destinationPath}")
        self.downloadFile(latestFile['id'], destinationPath)
        logger.info(f"✅ Download complete: {destinationPath}")
        
        return destinationPath


def main():
    """Automatically fetch the latest Excel file from 'Nhu Tin' folder."""
    driveFetcher = DriveFetcher()
    
    # Fetch latest Excel from "Nhu Tin" folder
    filePath = driveFetcher.fetchLatestExcelFromFolder("Nhu Tin")
    
    if filePath:
        logger.info(f"\n🎉 Success! File saved to: {filePath}")
    else:
        logger.error("\n❌ Failed to fetch file")


if __name__ == "__main__":
    main()
