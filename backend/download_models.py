import os
from huggingface_hub import snapshot_download

def download_models():
    # Define local directory within the backend folder
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models_data")
    
    os.makedirs(models_dir, exist_ok=True)
    
    print(f"🚀 Starting model downloads into: {models_dir}")
    
    # 1. Download Veena TTS
    print("\n📦 Downloading maya-research/Veena...")
    veena_path = os.path.join(models_dir, "Veena")
    snapshot_download(
        repo_id="maya-research/Veena",
        local_dir=veena_path,
        local_dir_use_symlinks=False
    )
    print(f"✅ Veena downloaded to {veena_path}")
    
    # 2. Download SNAC Codec
    print("\n📦 Downloading hubertsiuzdak/snac_24khz...")
    snac_path = os.path.join(models_dir, "snac_24khz")
    snapshot_download(
        repo_id="hubertsiuzdak/snac_24khz",
        local_dir=snac_path,
        local_dir_use_symlinks=False
    )
    print(f"✅ SNAC downloaded to {snac_path}")

    print("\n✨ All models downloaded successfully!")

if __name__ == "__main__":
    download_models()
