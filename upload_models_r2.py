#!/usr/bin/env python3
"""
Upload RustRelay models to Cloudflare R2.

Uses MD5 checksums to skip files that are already up-to-date.
Requires: pip install boto3

Environment variables:
  R2_ACCOUNT_ID        - Cloudflare account ID
  R2_ACCESS_KEY_ID     - R2 access key
  R2_SECRET_ACCESS_KEY - R2 secret key
  R2_BUCKET_NAME       - Target bucket name (default: rustrelay-models)
  R2_PUBLIC_URL        - Public URL of the bucket (for models-url attribute)

Usage:
  python scripts/upload_models_r2.py [--prefix mdl] [--source ../RustRelayViewer/wwwroot/mdl]
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import boto3
    from botocore.config import Config
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


def md5_file(path: Path) -> str:
    """Compute MD5 hex digest of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def get_content_type(filename: str) -> str:
    """Map file extension to MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    types = {
        "glb": "model/gltf-binary",
        "gltf": "model/gltf+json",
        "bin": "application/octet-stream",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    return types.get(ext, "application/octet-stream")


def main():
    parser = argparse.ArgumentParser(description="Upload models to Cloudflare R2")
    parser.add_argument(
        "--source",
        default=str(Path(__file__).parent.parent / "RustRelayViewer" / "wwwroot" / "mdl"),
        help="Path to the models directory",
    )
    parser.add_argument("--prefix", default="rrcdn/mdl", help="Key prefix in R2 bucket")
    parser.add_argument("--workers", type=int, default=16, help="Upload parallelism")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    args = parser.parse_args()

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("R2_BUCKET_NAME", "rustrelay-models")

    if not all([account_id, access_key, secret_key]):
        print("ERROR: Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY environment variables")
        sys.exit(1)

    source_dir = Path(args.source).resolve()
    if not source_dir.is_dir():
        print(f"ERROR: Source directory not found: {source_dir}")
        sys.exit(1)

    # Connect to R2
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    # List existing objects and their ETags (MD5 for non-multipart uploads)
    print(f"Scanning existing objects in {bucket_name}/{args.prefix}/...")
    existing: dict[str, str] = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Prefix=f"{args.prefix}/"):
        for obj in page.get("Contents", []):
            # ETag is quoted MD5 for standard uploads
            etag = obj["ETag"].strip('"')
            existing[obj["Key"]] = etag

    print(f"  Found {len(existing)} existing objects")

    # Scan local files (lowercase all keys for case-insensitive CDN access)
    local_files: list[tuple[Path, str]] = []  # (local_path, r2_key)
    for path in source_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(source_dir).as_posix().lower()
            key = f"{args.prefix}/{relative}"
            local_files.append((path, key))

    print(f"  Found {len(local_files)} local files")

    # Determine which files need uploading
    to_upload: list[tuple[Path, str]] = []
    skipped = 0

    for local_path, key in local_files:
        local_md5 = md5_file(local_path)
        remote_md5 = existing.get(key)
        if remote_md5 == local_md5:
            skipped += 1
        else:
            to_upload.append((local_path, key))

    print(f"\n  Skipping {skipped} unchanged files")
    print(f"  Uploading {len(to_upload)} new/modified files")

    if not to_upload:
        print("\nAll models are up-to-date!")
        return

    if args.dry_run:
        print("\n[DRY RUN] Would upload:")
        for path, key in to_upload[:20]:
            print(f"  {key} ({path.stat().st_size / 1024:.1f} KB)")
        if len(to_upload) > 20:
            print(f"  ... and {len(to_upload) - 20} more")
        return

    # Upload with progress
    uploaded = 0
    failed = 0
    total_bytes = sum(p.stat().st_size for p, _ in to_upload)

    def upload_file(item: tuple[Path, str]) -> tuple[bool, str]:
        local_path, key = item
        try:
            content_type = get_content_type(local_path.name)
            s3.upload_file(
                str(local_path),
                bucket_name,
                key,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
            return True, key
        except Exception as e:
            return False, f"{key}: {e}"

    print(f"\nUploading {len(to_upload)} files ({total_bytes / (1024*1024):.1f} MB total)...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(upload_file, item): item for item in to_upload}
        for future in as_completed(futures):
            success, msg = future.result()
            if success:
                uploaded += 1
            else:
                failed += 1
                print(f"  FAILED: {msg}")

            total = uploaded + failed
            if total % 100 == 0 or total == len(to_upload):
                print(f"  Progress: {total}/{len(to_upload)} ({uploaded} ok, {failed} failed)")

    print(f"\nDone! Uploaded: {uploaded}, Failed: {failed}, Skipped: {skipped}")

    public_url = os.environ.get("R2_PUBLIC_URL", "https://<your-r2-domain>")
    print(f'\nUse models-url attribute: models-url="{public_url}/{args.prefix}"')


if __name__ == "__main__":
    main()
