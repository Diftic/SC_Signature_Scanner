#!/usr/bin/env python3
"""
JXR to PNG converter using Windows WIC (native, no external tools needed).
"""

import subprocess
import sys
from pathlib import Path


def convert_jxr_to_png(jxr_path: Path, output_path: Path = None) -> Path:
    """Convert JXR to PNG using Windows WIC decoder via PowerShell."""
    
    if output_path is None:
        output_path = jxr_path.with_suffix('.png')
    
    # PowerShell script using WPF's built-in JXR decoder
    ps_script = f'''
Add-Type -AssemblyName PresentationCore

$inputPath = "{jxr_path}"
$outputPath = "{output_path}"

try {{
    $stream = [System.IO.File]::OpenRead($inputPath)
    $decoder = New-Object System.Windows.Media.Imaging.WmpBitmapDecoder(
        $stream,
        [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat,
        [System.Windows.Media.Imaging.BitmapCacheOption]::Default
    )
    $frame = $decoder.Frames[0]
    
    $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($frame))
    
    $outStream = [System.IO.File]::Create($outputPath)
    $encoder.Save($outStream)
    $outStream.Close()
    $stream.Close()
    
    Write-Output "SUCCESS"
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
'''
    
    result = subprocess.run(
        ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if 'SUCCESS' in result.stdout and output_path.exists():
        return output_path
    else:
        raise RuntimeError(f"Conversion failed: {result.stderr}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python jxr_converter.py <input.jxr> [output.png]")
        print("\nConverts JXR files to PNG using Windows native WIC decoder.")
        sys.exit(1)
    
    jxr_path = Path(sys.argv[1])
    if not jxr_path.exists():
        print(f"Error: File not found: {jxr_path}")
        sys.exit(1)
    
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    try:
        result = convert_jxr_to_png(jxr_path, output_path)
        print(f"Converted: {jxr_path.name} -> {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
