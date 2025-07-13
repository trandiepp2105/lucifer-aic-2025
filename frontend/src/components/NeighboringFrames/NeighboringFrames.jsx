import React, { useEffect, useRef, useState } from 'react';
import FrameItem from '../FrameItem/FrameItem';
import './NeighboringFrames.scss';

const NeighboringFrames = ({ selectedFrame, isVisible, onToggle, onFrameSelect, onFrameDoubleClick, onSubmit, onSend, queryMode = 'kis', sendingFrames = new Set() }) => {
  const selectedFrameRef = useRef(null);
  const neighboringFramesRef = useRef(null);
  const [frameCount, setFrameCount] = useState(30); // Default 100 frames

  // Generate neighboring frames based on selected frame and frame count
  const generateNeighboringFrames = (centerFrame, count) => {
    if (!centerFrame || !centerFrame.frame_index) return [];
    
    const frames = [];
    const centerFrameIndex = parseInt(centerFrame.frame_index);
    
    // Generate 'count' frames before and 'count' frames after (only frame_index divisible by 7)
    for (let i = -count; i <= count; i++) {
      const targetFrameIndex = centerFrameIndex + (i * 7);
      
      // Skip if frame index would be negative
      if (targetFrameIndex < 0) continue;
      
      let frameData;
      
      if (i === 0) {
        // This is the center frame (selected frame) - use as-is with isCenter flag
        frameData = {
          url: centerFrame.url,
          video_name: centerFrame.video_name,
          frame_index: centerFrame.frame_index,
          isCenter: true,
          offset: 0
        };
      } else {
        // Create new frame URL by replacing frame_index in the original URL
        const baseUrl = centerFrame.url;
        const newUrl = baseUrl.replace(
          `/${centerFrameIndex}.jpg`, 
          `/${targetFrameIndex}.jpg`
        );
        
        frameData = {
          url: newUrl,
          video_name: centerFrame.video_name,
          frame_index: targetFrameIndex,
          isCenter: false,
          offset: i
        };
      }
      
      frames.push(frameData);
    }
    
    return frames;
  };

  const neighboringFrames = generateNeighboringFrames(selectedFrame, frameCount);

  // Auto scroll to selected frame when component becomes visible
  useEffect(() => {
    if (isVisible && selectedFrameRef.current && neighboringFramesRef.current) {
      const timeout = setTimeout(() => {
        const contentContainer = neighboringFramesRef.current.querySelector('.neighboring-frames__content');
        const centerFrameWrapper = selectedFrameRef.current;
        
        if (centerFrameWrapper && contentContainer) {
          // Get all frame wrappers to find the index of center frame
          const allFrameWrappers = contentContainer.querySelectorAll('.neighboring-frames__frame-wrapper');
          const centerFrameIndex = Array.from(allFrameWrappers).indexOf(centerFrameWrapper);
          
          if (centerFrameIndex >= 0) {
            // Use fixed height for simple and accurate calculation
            const frameHeight = 160; // Fixed height from CSS
            const gap = 12.8; // 0.8rem gap (0.8 * 16px)
            const itemHeight = frameHeight + gap;
            const containerHeight = contentContainer.clientHeight;
            
            // Calculate scroll to center the specific frame
            const targetScrollTop = (centerFrameIndex * itemHeight) - (containerHeight / 2) + (frameHeight / 2);
            
            // Scroll immediately without animation for instant response
            contentContainer.scrollTop = Math.max(0, targetScrollTop);
          }
        }
      }, 100); // Small delay to ensure DOM is ready

      return () => clearTimeout(timeout);
    }
  }, [isVisible, selectedFrame?.video_name, selectedFrame?.frame_index, frameCount]);

  if (!isVisible) {
    return (
      <div className="neighboring-frames neighboring-frames--collapsed">
        <button 
          className="neighboring-frames__toggle"
          onClick={onToggle}
          title="Show neighboring frames"
        >
          <span>◀</span>
        </button>
      </div>
    );
  }

  return (
    <div className="neighboring-frames" ref={neighboringFramesRef}>
      <div className="neighboring-frames__header">
        <div className="neighboring-frames__controls">
          <label className="neighboring-frames__label">
            Frames:
            <input
              type="number"
              min="1"
              max="500"
              value={frameCount}
              onChange={(e) => setFrameCount(parseInt(e.target.value) || 1)}
              className="neighboring-frames__input"
              title="Number of frames to show before and after the selected frame"
            />
          </label>
        </div>
        <button 
          className="neighboring-frames__close"
          onClick={onToggle}
          title="Hide neighboring frames"
        >
          <span>▶</span>
        </button>
      </div>
      
      <div className="neighboring-frames__content">
        
        {neighboringFrames.length > 0 && (
          <div className="neighboring-frames__list">
            
            <div className="neighboring-frames__grid">
              {neighboringFrames.map((frame) => (
                <div
                  key={`${frame.video_name}-${frame.frame_index}`}
                  ref={frame.isCenter ? selectedFrameRef : null}
                  className={`neighboring-frames__frame-wrapper ${
                    frame.isCenter ? 'neighboring-frames__frame-wrapper--center' : ''
                  }`}
                  data-frame-id={`${frame.video_name}-${frame.frame_index}`}
                  data-frame-index={frame.frame_index}
                  data-is-center={frame.isCenter}
                >
                  <FrameItem
                    frame={frame}
                    isSelected={
                      // Check if this frame matches the selected frame by video_name and frame_index
                      selectedFrame && 
                      selectedFrame.video_name === frame.video_name && 
                      parseInt(selectedFrame.frame_index) === parseInt(frame.frame_index)
                    }
                    isCenter={frame.isCenter}
                    onClick={(clickedFrame) => {
                      if (onFrameSelect) {
                        onFrameSelect(clickedFrame);
                      }
                    }}
                    onDoubleClick={(clickedFrame) => {
                      if (onFrameDoubleClick) {
                        onFrameDoubleClick(clickedFrame);
                      }
                    }}
                    onSubmit={onSubmit}
                    onSend={onSend}
                    showFilename={true}
                    size="small"
                    className="neighboring-frames__frame"
                    isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NeighboringFrames;
