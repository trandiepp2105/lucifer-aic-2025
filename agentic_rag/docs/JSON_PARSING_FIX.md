# Fix for JSON Parsing and Response Format Errors

## Issues Fixed

### 1. JSON Parsing Error in Tools
**Problem**: The `temporal_frame_search_topk` and other tools were failing with a JSON decoding error when receiving input from LangGraph agents. The error occurred because the agent was wrapping JSON action inputs in markdown code fences (```json ... ```), which the JSON parser couldn't handle.

**Error Message**:
```
1 validation error for TemporalSearchInput
__root__
  Expecting value: line 1 column 1 (char 0) [type=value_error.jsondecode, input_value='```json\n{\n  "query_seq...n  ],\n  "k": 3\n}\n```', input_type=str]
```

**Solution**: Added `strip_markdown_code_fences()` utility function and updated all tool functions to preprocess input.

### 2. Agent Response Format Error
**Problem**: The agent was returning descriptive natural language responses instead of the expected JSON format, causing the API to fail with "Agent did not return a valid result" errors.

**Example Error**:
```json
{
  "success": false,
  "error_type": "agent_error",
  "error_message": "Agent did not return a valid result: The frames successfully match the description..."
}
```

**Solution**: Updated the agent's system prompt to explicitly require JSON output format and added a fallback response parser.

## Implementation Details

### Tool Input Processing Fix
1. **Added utility function** `strip_markdown_code_fences()` in `app/utils.py` to remove markdown code fences from JSON input.

2. **Updated all tool functions** that use `parse_raw()` to preprocess input:
   - `search_frames()`
   - `temporal_frame_search_topk()`
   - `get_video()`
   - `grid_search()`
   - `valid_frame_query()`

3. **Fix pattern** applied consistently:
   ```python
   # Before
   parsed_input = ModelClass.parse_raw(input_params)
   
   # After
   clean_input = strip_markdown_code_fences(input_params)
   parsed_input = ModelClass.parse_raw(clean_input)
   ```

### Agent Response Format Fix
1. **Updated system prompt** in `agent_core.py` to explicitly require JSON output:
   ```
   PHASE 4 - CONCLUSION:
   - If any strategy produces validated frame results, your Final Answer MUST be:
     {
       "success": true,
       "frames": ["frame_url_1", "frame_url_2", ...],
       "confidence_score": 0.85,
       "reasoning": "Detailed explanation"
     }
   - If all strategies fail, your Final Answer MUST be:
     {
       "success": false,
       "error": "Detailed explanation"
     }
   ```

2. **Added fallback response parser** `_extract_structured_info_from_text()` that can extract structured information from natural language responses as a safety net.

3. **Escaped JSON examples** in prompt template using double curly braces to prevent template variable conflicts.

## Testing Results

- ✅ The demo monitoring script now runs successfully without JSON parsing errors
- ✅ All tools can handle both plain JSON and markdown-wrapped JSON inputs
- ✅ The agent now returns properly formatted JSON responses
- ✅ API endpoints receive the expected response structure
- ✅ Both success and failure cases return proper JSON format

## Files Modified
- `app/utils.py` - Added `strip_markdown_code_fences()` function
- `app/tools.py` - Updated all functions using `parse_raw()` to strip markdown fences
- `app/agent_core.py` - Updated system prompt for JSON output requirement and added fallback parser

## Example of Fixed Output

**Before (causing errors)**:
```
The frames successfully match the description of Christmas decorations in a European city...
```

**After (proper JSON)**:
```json
{
  "success": true,
  "frames": ["L05_V027/23198.jpg", "L05_V027/23583.jpg", "L05_V027/23674.jpg"],
  "confidence_score": 0.88,
  "reasoning": "Found frames matching Christmas decorations in European city with decorative lights"
}
```

This comprehensive fix ensures robust JSON parsing and response formatting regardless of how the LangGraph agent formats its inputs and outputs.
