"""
Agent core functionality using LangChain for orchestrating the video retrieval process.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

from .config import config
from .tools import (
    temporal_frame_search_topk,
    # get_frame,
    grid_search,
    valid_frame_query
    # result_synthesizer (đã loại bỏ)
)
from .schemas import AgentResult, VideoSearchResponse, ErrorResponse, SynthesisInput
from .monitoring import get_monitor
from .callbacks import AgentMonitoringCallback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoRetrievalAgent:
    """
    Main agent class that orchestrates the video retrieval process.
    """
    
    def __init__(self):
        """Initialize the agent with LLM and tools."""
        self.llm = None
        self.agent_executor = None
        self.monitor = get_monitor()
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the LangChain agent with Gemini LLM and tools."""
        try:
            # Initialize Gemini LLM
            self.llm = ChatGoogleGenerativeAI(
                model=config.GEMINI_MODEL.replace("-vision", ""),  # Use text model for agent reasoning
                google_api_key=config.GOOGLE_API_KEY,
                temperature=config.GEMINI_TEMPERATURE,
                max_output_tokens=config.GEMINI_MAX_TOKENS
            )
            
            # Define tools
            tools = [
                Tool(
                    name="temporal_frame_search_topk",
                    func=temporal_frame_search_topk,
                    description="The most important tool for handling queries related to temporal event sequences with support for both text and OCR search. Use when the user describes a scenario with multiple actions occurring in succession (e.g., 'A does X, then B does Y'). This tool searches for frame sequences in the data store that match this description sequence and returns the most likely matching sequences. Input: query_sequence (List[Dict] where each dict can contain 'text' and/or 'ocr' fields), k (int), weights (optional Dict for text/ocr weights). Output: JSON with 'results' containing an array of {'sequence_score': float, 'frames': List[str]}."
                ),
                Tool(
                    name="grid_search",
                    func=grid_search,
                    description="""🔍 GRID SEARCH - Priority tool for batch frame analysis and comparison.

CRITICAL: This tool is highly efficient and should be your GO-TO choice when you have multiple frames to analyze (3+ frames).

🎯 KEY CAPABILITIES:
- Creates visual grids from multiple frames for simultaneous analysis
- Saves 80-90% API calls compared to individual frame analysis
- Supports comparison and relationship finding between frames
- Two modes: Legacy (simple) and Enhanced (advanced multi-group)

⚡ WHEN TO USE (HIGH PRIORITY):
✅ After getting frame URLs from temporal_frame_search_topk
✅ Need to evaluate/compare 3-20 frames simultaneously
✅ Finding the best frame among candidates
✅ Comparing multiple frame sequences from different searches
✅ Quick validation of frame suitability

📋 INPUT FORMATS:

LEGACY MODE (Simple):
{{
    "frame_urls": ["url1", "url2", ...],
    "grid_dimensions": [rows, cols],
    "query": "Specific analysis question in English"
}}

ENHANCED MODE (Multi-group comparison):
{{
    "frame_groups": [["group1_urls"], ["group2_urls"]],
    "group_queries": ["Query for group 1", "Query for group 2"],
    "comparison_query": "Question comparing groups",
    "layout_mode": "separate" or "combined"
}}

💡 USAGE EXAMPLES:
- "Which frame shows person A wearing red shirt most clearly?"
- "Among these 6 frames, which has the best image quality?"
- "Compare these two frame sequences - which happened first?"

⚠️ REQUIREMENTS:
- All queries MUST be in English
- Be specific in questions (avoid vague queries like "analyze this")
- Prefer this over valid_frame_query for multiple frames
- Maximum 20 frames per call for optimal performance"""
                ),
                Tool(
                    name="valid_frame_query",
                    func=valid_frame_query,
                    description="Validates whether a sequence of individual frames matches a corresponding sequence of descriptions. Use when detailed frame-by-frame checking is needed. This tool is less efficient than grid_search if only an overall assessment is required. Input: frames (List[str]), queries (List[str]). Output: JSON with 'overall_match' (boolean), 'confidence_score' (float), 'reasoning' (string), 'details' (List[dict])."
                )
                # Tool result_synthesizer đã bị loại bỏ
            ]
            
            # Create system prompt
            system_prompt = self._create_system_prompt()
            
            # Create agent
            agent = create_react_agent(
                llm=self.llm,
                tools=tools,
                prompt=system_prompt
            )
            
            # Create executor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                max_iterations=60,
                max_execution_time=600,
                handle_parsing_errors=True,
                return_intermediate_steps=True,
                callbacks=[AgentMonitoringCallback()]
            )
            
            logger.info("Agent setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up agent: {str(e)}")
            raise
    
    def _create_system_prompt(self) -> PromptTemplate:
        """Create the system prompt template for the agent."""
        template = """SYSTEM PROMPT - FRAME RETRIEVAL AND ANALYSIS AGENT V4 (MULTI-STRATEGY)
1. CORE ROLE AND OBJECTIVES
You are an expert AI Agent, designed to be a "Frame Retrieval and Analysis Specialist". Your primary mission is to deeply understand user requirements, utilizing a specialized set of tools to search, extract, and validate content from a large frame/image archive extracted from videos.

Your ultimate goal is to provide accurate, evidence-based, and reliable answers to users. You must act methodically, efficiently, and always prioritize using tools to gather information rather than relying on internal knowledge.

IMPORTANT: You are searching through FRAMES (individual images) extracted from videos, NOT videos themselves. When users ask about "videos", you should interpret this as searching for relevant frames that match their description.

Contextual Information:
Current Date and Time: {{current_datetime}} (This value will be automatically populated at runtime)

2. OPERATIONAL PRINCIPLES
STEP-BY-STEP THINKING: Always break down complex requests into logical, manageable steps. Document your thought process in the `thought` section to clarify why you chose a specific action.

TOOL-FIRST APPROACH: You DO NOT have the ability to "watch" videos or "remember" content. All media information must be gathered by calling the provided tools.

FRAME-BASED SEARCH UNDERSTANDING: 
- You search through individual frames (images) extracted from videos
- When users describe "video content", translate this into frame descriptions
- Focus on visual elements that can be captured in a single frame or sequence of frames
- Think in terms of "what would this look like in a photograph" rather than "what happens in a video"
- For text elements (signs, labels, captions, etc.), preserve the original language without diacritics (e.g., "Hello World" not "Héllö Wörld")
- Use OCR search when looking for specific text content in frames (signs, labels, captions, subtitles, etc.)
- You can combine text and OCR search in the same query_sequence for better results

OPTIMIZATION AND EFFICIENCY: Always choose the most appropriate and efficient tool for the task. CRITICAL PRIORITY ORDER:

🥇 GRID_SEARCH FIRST: When you have multiple frames to analyze (3+), ALWAYS use `grid_search` as your primary tool:
- Saves 80-90% API calls compared to individual analysis
- Allows direct frame comparison and relationship finding
- More effective for finding "best" frames among candidates
- Should be your GO-TO tool after temporal_frame_search_topk

🥈 VALID_FRAME_QUERY ONLY WHEN: Use only for detailed, frame-by-frame validation when grid_search isn't sufficient:
- When you need frame-by-frame detailed analysis
- When grid_search results need additional validation
- Only after trying grid_search first

🥉 TEMPORAL_FRAME_SEARCH_TOPK: Primary search tool for finding frame candidates
- Use this to get initial frame URLs
- Then feed results to grid_search for analysis

EFFICIENCY RULE: NEVER call valid_frame_query multiple times when you could use grid_search once!

LANGUAGE REQUIREMENT: All search-related tool calls (such as `temporal_frame_search_topk`, `grid_search`, `valid_frame_query`) MUST use English descriptions, regardless of the user's query language. If the user provides a query in another language, you must translate it to English before using it as input for these tools.

TEXT ELEMENT HANDLING: When describing text elements in frames (signs, labels, captions, subtitles, etc.):
- Preserve the original language of the text without diacritics
- Use plain ASCII characters (e.g., "Cafe" not "Café", "Hello" not "Héllö")
- Keep the text exactly as it appears visually in the frame
- Do not translate text elements unless specifically requested
- Examples: "STOP" sign, "Welcome" banner, "Exit" door sign
- For text search, use the 'text' field in query_sequence
- For OCR search, use the 'ocr' field in query_sequence with the exact text to find
- You can use both 'text' and 'ocr' in the same stage for comprehensive search

VALIDATION STRATEGY: 
🎯 PRIMARY: Use `grid_search` as your main validation tool for multiple frames:
- Group frames logically (same sequence, same topic, same camera angle)
- Create specific, actionable queries for analysis
- Use legacy mode for simple comparisons, enhanced mode for complex multi-group analysis

🔍 SECONDARY: Use `valid_frame_query` only when grid_search results need additional detail:
- For frame-by-frame breakdown when grid_search provides insufficient detail
- For final validation of 1-2 specific frames
- Never as a replacement for grid_search when you have multiple frames

💡 BEST PRACTICE: temporal_frame_search_topk → grid_search → (optional) valid_frame_query

MULTI-STRATEGY APPROACH: When initial searches don't find results, systematically try different query strategies before giving up. This is CRITICAL for maximizing search success.

3. AVAILABLE TOOLS
You have access to the following tools. Use them strictly according to their described functions.

{tools}

4. WORKFLOW AND REASONING STRATEGIES

PHASE 0 - TRANSLATE AND PREPARE QUERY (ALWAYS FIRST)
- Thought: "First, I need to translate the user's query or list of queries to English, keeping the list structure if present."
- Action: Translate the query or each item in the list to English, but keep the structure and meaning exactly as the original, do not split or merge, do not add or remove any stages or steps.
- Action: For each query, if there are text elements that should be searched by OCR (e.g., signs, captions), add an 'ocr' field with the exact text (without diacritics, in ASCII).
- Action: Prepare the query_sequence (list of dicts with 'text' and/or 'ocr' fields) for searching.
- Action: Use `temporal_frame_search_topk` with the prepared query_sequence as the first search step.

Scenario 1: Frame-Based Search Query with Multi-Strategy Fallback
When: The user describes a scenario, e.g., "Find frames showing a blue car driving, then turning right and stopping." Or a simple event, e.g., "Find frames with a barking dog."

Process:
PHASE 1 - PRIMARY SEARCH:
- Thought: "Dịch và giữ nguyên query, không phân stage, không tách nhỏ, không gom lại, không thêm bước, không thay đổi cấu trúc. Chỉ dịch sang tiếng Anh và giữ nguyên list nếu có."
- Action: Dịch toàn bộ query hoặc từng phần tử trong list sang tiếng Anh, giữ nguyên cấu trúc, không chia nhỏ, không gom lại, không thêm bước, không thay đổi thứ tự.
- Action: Nếu có text cần tìm bằng OCR (ví dụ: biển báo, caption), thêm trường 'ocr' với nội dung text đó (không dấu, ASCII).
- Action: Chuẩn bị query_sequence (list các dict với 'text' và/hoặc 'ocr') để tìm kiếm.
- Action: Gọi `temporal_frame_search_topk` với query_sequence đã chuẩn bị.
- Observation: Nhận về danh sách các candidate frame sequence.

PHASE 2 - QUICK VALIDATION OF TOP CANDIDATES:
- Thought: "To quickly filter and identify the most promising candidates, I will use `grid_search` to validate the top ~12 candidate frames or sequences at once."
- Action: Lấy tối đa 12 candidate frame sequences (hoặc frames) từ kết quả search đầu tiên. Nếu có ít hơn 12, lấy tất cả; nếu nhiều hơn, lấy 12.
- Action: Luôn đảm bảo sử dụng ít nhất 12 ảnh (nếu có đủ) khi gọi `grid_search` để đánh giá nhanh. (lưu ý ảnh có kích thước là 640x480 nên cần sắp xếp grid cho cần đối thay vì một chiều dài, một chiều ngắn (3 và 4))
- Action: Gọi `grid_search` với danh sách các frame này để đánh giá nhanh
- Observation: Nhận kết quả đánh giá từ `grid_search` để xác định các ứng viên tốt nhất.
- Nếu có ứng viên phù hợp, chuyển sang PHASE 4 - CONCLUSION.
- Nếu chưa có, tiếp tục các chiến lược fallback ở PHASE 2 dưới đây.

PHASE 2 - VALIDATION AND FALLBACK STRATEGIES:
If initial search returns no results or all candidates fail validation, proceed through these strategies in order:

Strategy 1: Broader/Simplified Frame Query
- Thought: "The original frame description might be too specific. Let me try a broader, simplified version focusing on key visual elements that can be captured in a single frame."
- Action: Extract main visual objects/actions and create a simplified frame query (e.g., "blue car" instead of "blue car driving, then turning right and stopping").
- Action: Call `temporal_frame_search_topk` with the simplified frame query.
- Observation: Check for results.

Strategy 2: Component-Based Frame Search
- Thought: "Let me break down the query into individual visual components that can be captured in separate frames."
- Action: Split the query into individual visual elements (e.g., ["blue car", "car turning", "car stopped"]).
- Action: Call `temporal_frame_search_topk` for each visual component individually.
- Observation: Collect all results and look for overlapping frame sequences.

Strategy 3: Alternative Frame Descriptions
- Thought: "Let me try alternative ways to describe the same visual elements using synonyms or related visual terms."
- Action: Create alternative visual descriptions (e.g., "vehicle" instead of "car", "stationary car" instead of "stopped car").
- Action: For text elements, try variations without diacritics or common misspellings (e.g., "Cafe" instead of "Café", "Stop" instead of "STOP").
- Action: For OCR search, try variations of text content (e.g., "STOP", "Stop", "stop" for stop signs).
- Action: Call `temporal_frame_search_topk` with alternative frame descriptions using text/ocr fields.
- Observation: Check for results.

Strategy 4: OCR-Focused Search
- Thought: "Let me focus on text content in frames using OCR search, especially if the query mentions specific text elements."
- Action: Extract text elements from the query and search using OCR (e.g., "{{"ocr"": ""Welcome""}}" for welcome signs).
- Action: Combine OCR with visual descriptions when appropriate (e.g., "{{"text"": ""blue car"", ""ocr"": ""STOP""}}").
- Action: Call `temporal_frame_search_topk` with OCR-focused queries.
- Observation: Check for results.

Strategy 5: Partial Visual Match Search
- Thought: "Let me search for partial visual matches that might contain some elements of the requested scene."
- Action: Focus on the most distinctive visual element of the query and search for it.
- Action: Call `temporal_frame_search_topk` with the most distinctive visual element.
- Observation: Check for results.

PHASE 3 - VALIDATION:
For each strategy that returns results:
- Iterate through candidates (best first):
    a. Thought: "Now I need to validate the candidate frames. I will prioritize `grid_search` for efficient batch analysis."
    
    🎯 GRID_SEARCH WORKFLOW:
    b. Action: Group frames logically:
       - Same temporal sequence together
       - Same topic/person together  
       - Same camera angle together
    
    c. Action: Choose appropriate grid_search mode:
       - LEGACY: Single group with one question
         Example: {{"frame_urls": [...], "query": "Which frame shows person wearing red shirt most clearly?"}}
       - ENHANCED: Multiple groups for comparison
         Example: {{"frame_groups": [[seq1], [seq2]], "comparison_query": "Which sequence happened first?"}}
    
    d. Action: Use `grid_search` with specific, actionable English queries:
       ✅ Good: "Which frame shows the clearest view of a blue car?"
       ❌ Bad: "Analyze these frames"
    
    e. Observation: Receive grid analysis results - look for confidence scores and specific frame recommendations.
    
    🔍 DETAILED VALIDATION (if needed):
    f. Action: Only if grid_search results need more detail, use `valid_frame_query` on 1-2 best frames identified by grid_search.
    g. Observation: Receive detailed validation results.
    h. If validation succeeds, proceed to conclusion.

PHASE 4 - CONCLUSION:
- If any strategy produces validated frame results, your Final Answer MUST be a properly formatted JSON object with the following structure:
  {{{{
    "success": true,
    "frames": ["frame_url_1", "frame_url_2", ...],
    "confidence_score": 0.85,
    "reasoning": "Detailed explanation of why these frames match the query"
  }}}}
- If all strategies are exhausted without success, your Final Answer MUST be:
  {{{{
    "success": false,
    "error": "Detailed explanation of all search attempts made and why no suitable frames were found"
  }}}}

Scenario 2: Frame-Based Question Answering with Multi-Strategy Fallback
When: The user asks a direct question about visual content, e.g., "How many people are in the frames showing a man in a red shirt riding a bicycle?"

Process:
- Thought: "The user has a specific question about visual content, but first I need to find the relevant frames using multiple strategies."
- Action: Extract the visual description (e.g., "man in a red shirt riding a bicycle") and use the multi-strategy process from Scenario 1 to find matching frames.
- In the final validation step, use `grid_search` or `valid_frame_query` to analyze the frames and answer the user's question about the visual content.
- Final Answer: Return a JSON object with the validation result and the answer to the question:
  {{{{
    "success": true,
    "frames": ["frame_url_1", "frame_url_2", ...],
    "confidence_score": 0.85,
    "reasoning": "Detailed explanation",
    "answer_to_question": "Answer to the specific question asked"
  }}}}

5. MANDATORY RULES
Output Format: All your thoughts and actions must strictly adhere to the required JSON format.

Never use get_frame as a final action or return its output to the user. get_frame is for internal use only to provide image data to validation tools (grid_search, valid_frame_query). The final answer must always be a properly formatted JSON object as specified above.

No Assumptions: If information is not returned by a tool, assume it does not exist. Do not infer.

Error Handling: If a tool returns an error, acknowledge it in the `observation` and try a different approach or tool if possible.

PERSISTENCE: You must try ALL available strategies before concluding that no match is found. Do not give up after the first failed attempt. This includes trying both text and OCR search approaches, as well as combinations of both.

Strategy Documentation: Always document which strategy you're using in your thoughts, and explain why you're moving to the next strategy.

5. GRID_SEARCH EXAMPLES AND BEST PRACTICES

📋 EXAMPLE 1 - Legacy Mode (Simple frame selection):
User: "Find the clearest image of a person wearing a red shirt"
After temporal_frame_search_topk returns 8 candidate frames:

Thought: "I have 8 candidate frames. I'll use grid_search to compare them and find the clearest one with a person in red shirt."
Action: grid_search
Action Input: {{
    "frame_urls": ["frame1.jpg", "frame2.jpg", "frame3.jpg", "frame4.jpg", "frame5.jpg", "frame6.jpg", "frame7.jpg", "frame8.jpg"],
    "grid_dimensions": [2, 4],
    "query": "Which frame shows the clearest and most visible person wearing a red shirt?"
}}

📋 EXAMPLE 2 - Enhanced Mode (Sequence comparison):
User: "Compare two different conversations to see which happened first"
After temporal_frame_search_topk returns two sequences:

Thought: "I have two conversation sequences. I'll use enhanced grid_search to compare them and determine temporal order."
Action: grid_search  
Action Input: {{
    "frame_groups": [
        ["conv1_frame1.jpg", "conv1_frame2.jpg", "conv1_frame3.jpg"],
        ["conv2_frame1.jpg", "conv2_frame2.jpg", "conv2_frame3.jpg"]
    ],
    "comparison_query": "Based on clothing, lighting, and context clues, which conversation sequence happened first chronologically?",
    "layout_mode": "separate"
}}

📋 EXAMPLE 3 - Multi-group analysis:
User: "Find frames showing: person A speaking, person B reacting, audience response"
After temporal_frame_search_topk returns multiple sequences:

Thought: "I have three different types of frames. I'll use enhanced grid_search to analyze each group and find the best examples."
Action: grid_search
Action Input: {{
    "frame_groups": [
        ["speaker_1.jpg", "speaker_2.jpg", "speaker_3.jpg"],
        ["reaction_1.jpg", "reaction_2.jpg", "reaction_3.jpg"],
        ["audience_1.jpg", "audience_2.jpg", "audience_3.jpg"]
    ],
    "group_queries": [
        "Which frame shows person A speaking most clearly?",
        "Which frame shows person B's reaction most distinctly?", 
        "Which frame shows the clearest audience response?"
    ],
    "comparison_query": "What is the logical sequence: speaking, reacting, then audience response?",
    "layout_mode": "separate"
}}

🚫 WHAT NOT TO DO:
❌ Don't use valid_frame_query multiple times when you could use grid_search once
❌ Don't use vague queries like "analyze these frames"
❌ Don't call grid_search with only 1-2 frames (use valid_frame_query instead)

JSON Final Answer Requirement: Your Final Answer MUST ALWAYS be a valid JSON object following the exact structure specified in PHASE 4 - CONCLUSION. Do NOT include any additional text or explanations outside the JSON object.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: MUST be a valid JSON object following the structure specified in PHASE 4 - CONCLUSION

Question: {input}
Thought: {agent_scratchpad}"""

                        
        return PromptTemplate(
            template=template,
            input_variables=["input", "tools", "tool_names", "agent_scratchpad"]
        )
    
    def _extract_structured_info_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract structured information from natural language agent response.
        
        Args:
            text: The natural language response from the agent
            
        Returns:
            Dict containing extracted structured information
        """
        import re
        
        try:
            # Initialize result structure
            result = {
                "success": False,
                "frames": [],
                "confidence_score": 0.0,
                "reasoning": ""
            }
            
            # Look for success indicators
            success_keywords = [
                "successfully match", "frames match", "found frames", "confirmed",
                "validation confirmed", "grid_search validation", "match the description"
            ]
            
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in success_keywords):
                result["success"] = True
            
            # Extract frame URLs using pattern matching
            frame_patterns = [
                r'L\d+_V\d+/\d+\.jpg',  # Pattern like L05_V027/23198.jpg
                r'frame[_\s]*urls?[:\s]*([^\n]+)',  # Look for frame urls
                r'matching[_\s]*frames?[:\s]*([^\n]+)'  # Look for matching frames
            ]
            
            frames = []
            for pattern in frame_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, str):
                        # Extract individual frame URLs from the match
                        frame_urls = re.findall(r'L\d+_V\d+/\d+\.jpg', match)
                        frames.extend(frame_urls)
            
            # Remove duplicates while preserving order
            seen = set()
            result["frames"] = [f for f in frames if not (f in seen or seen.add(f))]
            
            # Extract confidence score
            confidence_patterns = [
                r'confidence[_\s]*score[:\s]*(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*confidence',
                r'score[:\s]*(\d+\.?\d*)'
            ]
            
            for pattern in confidence_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    try:
                        score = float(matches[0])
                        if score > 1.0:
                            score = score / 100.0  # Convert percentage
                        result["confidence_score"] = min(1.0, max(0.0, score))
                        break
                    except ValueError:
                        continue
            
            # If no confidence score found but frames were found, use default
            if result["frames"] and result["confidence_score"] == 0.0:
                result["confidence_score"] = 0.7  # Default reasonable confidence
            
            # Extract reasoning (use the full text as reasoning, cleaned up)
            reasoning_lines = []
            for line in text.split('\n'):
                line = line.strip()
                if line and not line.startswith('**') and not line.startswith('#'):
                    reasoning_lines.append(line)
            
            result["reasoning"] = ' '.join(reasoning_lines[:5])  # Limit to first 5 lines
            
            # Final validation - must have frames for success
            if result["success"] and not result["frames"]:
                result["success"] = False
                result["reasoning"] = "No frame URLs could be extracted from the response"
            
            logger.info(f"Extracted structured info: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting structured info: {e}")
            return {
                "success": False,
                "frames": [],
                "confidence_score": 0.0,
                "reasoning": f"Error parsing response: {str(e)}"
            }
    
    def find_video(self, descriptions: List[str]) -> Dict[str, Any]:
        """
        Main method to find video based on description.
        
        Args:
            description (str): User's description of the desired video
            
        Returns:
            Dict[str, Any]: Result containing video info or error
        """
        try:
            logger.info(f"Starting video search for: {descriptions}")
            
            # Start monitoring session
            query_str = " | ".join(descriptions) if isinstance(descriptions, list) else str(descriptions)
            session_id = self.monitor.start_session(query_str)
            
            try:
                # Execute agent
                result = self.agent_executor.invoke({
                    "input": f"Find video matching description: {descriptions}"
                })
                
                # Parse agent output
                agent_output = result.get("output", "")
                intermediate_steps = result.get("intermediate_steps", [])
                
                logger.info(f"Agent output: {agent_output}")
                
                # Try to extract JSON from agent output (could be in Final Answer or direct output)
                try:
                    # Look for JSON in the output - first try to find complete JSON
                    json_str = None
                    
                    # Check if output contains Final Answer format
                    if "Final Answer:" in agent_output:
                        # Extract everything after "Final Answer:"
                        final_answer_start = agent_output.find("Final Answer:") + len("Final Answer:")
                        final_answer_content = agent_output[final_answer_start:].strip()
                        
                        # Look for JSON in final answer
                        start_idx = final_answer_content.find('{')
                        end_idx = final_answer_content.rfind('}') + 1
                        if start_idx != -1 and end_idx != 0:
                            json_str = final_answer_content[start_idx:end_idx]
                    else:
                        # Look for JSON anywhere in the output
                        start_idx = agent_output.find('{')
                        end_idx = agent_output.rfind('}') + 1
                        if start_idx != -1 and end_idx != 0:
                            json_str = agent_output[start_idx:end_idx]
                    
                    if json_str:
                        parsed_result = json.loads(json_str)
                        
                        if parsed_result.get("success", False):
                            # End session successfully
                            self.monitor.end_session(
                                final_answer=json_str,
                                success=True
                            )
                            
                            # Adapt to VideoSearchResponse: frames, confidence_score, reasoning
                            return {
                                "success": True,
                                "frames": parsed_result.get("frames", []),
                                "confidence_score": parsed_result.get("confidence_score", 0.0),
                                "reasoning": parsed_result.get("reasoning", "")
                            }
                        else:
                            # End session with failure
                            error_msg = parsed_result.get("error", "No suitable video found")
                            self.monitor.end_session(
                                final_answer=json_str,
                                success=False,
                                error_message=error_msg
                            )
                            
                            return {
                                "success": False,
                                "error_type": "no_match",
                                "error_message": error_msg
                            }
                    else:
                        # If no JSON found, try to extract structured information from the text
                        logger.warning("No JSON found in agent output, attempting to extract structured information")
                        parsed_result = self._extract_structured_info_from_text(agent_output)
                        
                        if parsed_result.get("success", False):
                            # End session successfully
                            json_str = json.dumps(parsed_result)
                            self.monitor.end_session(
                                final_answer=json_str,
                                success=True
                            )
                            
                            return {
                                "success": True,
                                "frames": parsed_result.get("frames", []),
                                "confidence_score": parsed_result.get("confidence_score", 0.0),
                                "reasoning": parsed_result.get("reasoning", "")
                            }
                        else:
                            # End session with failure
                            error_msg = f"Agent did not return a valid result: {agent_output}"
                            self.monitor.end_session(
                                final_answer=agent_output,
                                success=False,
                                error_message=error_msg
                            )
                            
                            return {
                                "success": False,
                                "error_type": "agent_error",
                                "error_message": error_msg
                            }
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing agent output as JSON: {e}")
                    error_msg = f"Error parsing agent result: {str(e)}"
                    self.monitor.end_session(
                        final_answer=agent_output,
                        success=False,
                        error_message=error_msg
                    )
                    
                    return {
                        "success": False,
                        "error_type": "parsing_error",
                        "error_message": error_msg
                    }
                    
            except Exception as e:
                # End session with error
                error_msg = f"Agent execution error: {str(e)}"
                self.monitor.end_session(
                    success=False,
                    error_message=error_msg
                )
                raise
                
        except Exception as e:
            logger.error(f"Error in find_video: {str(e)}")
            return {
                "success": False,
                "error_type": "system_error",
                "error_message": f"System error: {str(e)}"
            }


# Global agent instance
_agent_instance = None


def get_agent() -> VideoRetrievalAgent:
    """
    Get or create the global agent instance.
    
    Returns:
        VideoRetrievalAgent: The agent instance
    """
    global _agent_instance
    
    if _agent_instance is None:
        # Validate configuration first
        config.validate_config()
        _agent_instance = VideoRetrievalAgent()
    
    return _agent_instance


def reset_agent():
    """Reset the global agent instance (useful for testing)."""
    global _agent_instance
    _agent_instance = None
