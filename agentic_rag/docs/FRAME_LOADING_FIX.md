# Fix for Frame Loading Error

## Issue
The frame viewer was attempting to load frame images directly from local file paths instead of fetching them from the media server via HTTP, causing the error:

```
Error loading image from L05_V027/23583.jpg: [Errno 2] No such file or directory: 'L05_V027/23583.jpg'
```

## Root Cause
In `app/frame_viewer.py`, the `load_image` method had a fallback case that tried to open frame URLs directly as local files:

```python
else:
    # Handle local file paths
    image = Image.open(frame_url)
```

However, frame URLs like "L05_V027/23583.jpg" are not local file paths - they are relative paths that need to be fetched from the media server.

## Solution
Updated the frame loading logic in `app/frame_viewer.py` to properly construct the media server URL for frame paths:

```python
else:
    # Handle frame paths by constructing proper media server URL
    # Frame paths like "L05_V027/23583.jpg" need to be fetched from media server
    # Use the same URL construction pattern as get_frames function
    full_url = f"{config.MEDIA_API_URL}/{frame_url}"
    response = requests.get(full_url, timeout=10)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content))
```

This follows the same pattern used in the `get_frames` function in `tools.py`.

## Testing
- ✅ Frame loading now works correctly for paths like "L05_V027/23583.jpg"
- ✅ Images are successfully fetched from the media server
- ✅ No syntax errors in the modified code

## Files Modified
- `app/frame_viewer.py` - Fixed frame loading logic and added config import

This fix ensures that the monitoring dashboard can properly display frame images without trying to access them as local files.
