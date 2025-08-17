# LangGraph Refactoring Documentation

## Overview

This document describes the complete refactoring of the agentic_rag project from LangChain to LangGraph. The refactoring improves workflow management, error handling, and maintainability while preserving the existing API interface.

## What Changed

### 1. New LangGraph Agent (`app/langgraph_agent.py`)

- **LangGraphVideoAgent**: New agent class using LangGraph workflows
- **Structured State Management**: Using `VideoRetrievalState` TypedDict for state management
- **Node-Based Workflow**: Clear separation of concerns with dedicated nodes:
  - `preprocess_query_node`: Query preprocessing and validation
  - `temporal_search_node`: Temporal frame search execution
  - `grid_search_node`: Grid search for candidate ranking
  - `validation_node`: Video validation and clip generation
  - `response_synthesis_node`: Final response formatting
  - `error_handler_node`: Error handling and fallback responses

### 2. Refactored Agent Core (`app/agent_core.py`)

- **Simplified VideoRetrievalAgent**: Now uses LangGraph agent internally
- **Maintained API Compatibility**: Same `find_video()` method signature
- **Better Error Handling**: Cleaner error propagation and logging
- **Removed LangChain Dependencies**: No more React agent patterns

### 3. Workflow Improvements

#### Before (LangChain):
```
User Input → React Agent → Tool Selection → Tool Execution → Response Parsing
```

#### After (LangGraph):
```
User Input → Preprocess → Temporal Search → Grid Search → Validation → Synthesis → Response
                 ↓           ↓              ↓           ↓            ↓
              Error ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←← Handler
```

## Key Benefits

### 1. **Better Control Flow**
- Explicit state transitions between workflow stages
- Conditional routing based on results
- Centralized error handling

### 2. **Improved Reliability**
- Better error recovery and fallback strategies
- State persistence across workflow steps
- Deterministic execution paths

### 3. **Enhanced Maintainability**
- Clear separation of concerns
- Easier to test individual workflow nodes
- Simpler debugging and monitoring

### 4. **Backward Compatibility**
- Existing API endpoints unchanged
- Same response format
- Drop-in replacement for existing implementation

## Migration Details

### Files Created:
- `app/langgraph_agent.py` - New LangGraph implementation
- `test_structure.py` - Structure validation tests
- `LANGGRAPH_REFACTORING.md` - This documentation

### Files Modified:
- `app/agent_core.py` - Refactored to use LangGraph agent
- `app/langgraph_search.py` - Cleaned up and simplified

### Files Unchanged:
- `app/main.py` - FastAPI endpoints (minimal changes)
- `app/tools.py` - All existing tools preserved
- `app/schemas.py` - All schemas preserved
- `app/config.py` - Configuration unchanged
- `requirements.txt` - LangGraph dependency already present

## Usage

### For Development:
```python
from app.langgraph_agent import get_langgraph_agent

# Get LangGraph agent directly
agent = get_langgraph_agent()
result = agent.find_video(["description here"])
```

### For Existing Code:
```python
from app.agent_core import get_agent

# Works exactly as before, but uses LangGraph internally
agent = get_agent()
result = agent.find_video(["description here"])
```

## Workflow Details

### State Management
The workflow uses a `VideoRetrievalState` TypedDict that tracks:
- User descriptions and preprocessed queries
- Results from each workflow stage
- Error information and success status
- Intermediate results for monitoring

### Node Functions
Each node is a pure function that takes the current state and returns updated state:

```python
def temporal_search_node(state: VideoRetrievalState) -> VideoRetrievalState:
    # Process temporal search
    # Update state with results
    # Return modified state
```

### Error Handling
- Each node handles its own errors gracefully
- Failed nodes update state with error information
- Conditional edges route to error handler when needed
- Error handler provides fallback responses

### Conditional Routing
- `should_continue_to_grid_search()`: Routes based on temporal search results
- `should_continue_to_validation()`: Routes based on grid search results  
- `should_continue_to_synthesis()`: Routes based on validation results

## Dependencies

The refactoring requires:
- `langgraph>=0.0.26` (already in requirements.txt)
- All existing dependencies preserved
- No new external dependencies added

## Testing

Run the structure tests to verify the refactoring:
```bash
cd /home/hkduy/workplace/lucifer-aic-2025/agentic_rag
python3 test_structure.py
```

## Future Enhancements

The LangGraph structure enables several future improvements:

1. **Parallel Processing**: Run multiple validation paths simultaneously
2. **Checkpointing**: Save/restore workflow state for long-running processes
3. **Dynamic Routing**: Adapt workflow based on content type or user preferences
4. **A/B Testing**: Compare different workflow configurations
5. **Monitoring**: Better observability into workflow execution

## Conclusion

This refactoring successfully modernizes the agentic_rag system by:
- Replacing complex LangChain agent patterns with structured LangGraph workflows
- Improving reliability and error handling
- Maintaining full backward compatibility
- Enabling future enhancements and optimizations

The system is now more maintainable, reliable, and ready for production use.
