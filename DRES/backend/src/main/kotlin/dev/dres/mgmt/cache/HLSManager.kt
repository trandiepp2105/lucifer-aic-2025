package dev.dres.mgmt.cache

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import kotlin.math.abs

/**
 * Represents an HLS segment with timing information
 */
data class HLSSegment(
    val path: Path,
    val duration: Double,
    val startTime: Double,
    val endTime: Double
)

/**
 * HLS playlist parser and segment manager
 * 
 * @author Generated for DRES HLS optimization
 * @version 1.0.0
 */
class HLSManager(private val baseVideoPath: Path) {
    
    companion object {
        private const val SEGMENT_TOLERANCE = 0.1 // 100ms tolerance
    }
    
    /**
     * Parse M3U8 playlist file and extract segment information
     * 
     * @param playlistPath Path to the M3U8 playlist file
     * @return List of HLS segments with timing information
     */
    fun parsePlaylist(playlistPath: Path): List<HLSSegment> {
        if (!Files.exists(playlistPath)) {
            throw IllegalArgumentException("Playlist file not found: $playlistPath")
        }
        
        val segments = mutableListOf<HLSSegment>()
        val lines = Files.readAllLines(playlistPath)
        val baseDir = playlistPath.parent
        
        var currentDuration = 0.0
        var currentStartTime = 0.0
        
        for (i in lines.indices) {
            val line = lines[i].trim()
            
            // Parse segment duration from #EXTINF:duration,title format
            if (line.startsWith("#EXTINF:")) {
                val extinf = line.substring(8) // Remove "#EXTINF:"
                val durationPart = extinf.split(",")[0] // Get duration part before comma
                currentDuration = try {
                    durationPart.toDouble()
                } catch (e: NumberFormatException) {
                    0.0 // Default to 0 if parsing fails
                }
            }
            // Parse segment file (any line that doesn't start with # and isn't empty)
            else if (!line.startsWith("#") && line.isNotEmpty()) {
                val segmentPath = baseDir.resolve(line)
                if (Files.exists(segmentPath)) {
                    val endTime = currentStartTime + currentDuration
                    segments.add(HLSSegment(
                        path = segmentPath,
                        duration = currentDuration,
                        startTime = currentStartTime,
                        endTime = endTime
                    ))
                    currentStartTime = endTime
                } else {
                    // Log warning but continue parsing
                    println("Warning: Segment file not found: $segmentPath")
                }
            }
        }
        
        return segments
    }
    
    /**
     * Find segments that overlap with the given time range
     * 
     * @param segments List of all segments
     * @param startTimeMs Start time in milliseconds
     * @param endTimeMs End time in milliseconds
     * @return List of segments that should be included
     */
    fun findSegmentsInRange(segments: List<HLSSegment>, startTimeMs: Long, endTimeMs: Long): List<HLSSegment> {
        val startTime = startTimeMs / 1000.0
        val endTime = endTimeMs / 1000.0
        
        return segments.filter { segment ->
            // Include segment if it overlaps with the requested time range
            segment.startTime < endTime + SEGMENT_TOLERANCE && 
            segment.endTime > startTime - SEGMENT_TOLERANCE
        }
    }
    
    /**
     * Get HLS directory path for a video name
     * 
     * @param videoName Name of the video (without extension)
     * @return Path to the HLS directory for this video
     */
    fun getHLSDirectory(videoName: String): Path {
        return baseVideoPath.resolve(videoName)
    }
    
    /**
     * Get playlist path for a video name
     * 
     * @param videoName Name of the video (without extension)
     * @return Path to the M3U8 playlist file
     */
    fun getPlaylistPath(videoName: String): Path {
        return getHLSDirectory(videoName).resolve("playlist.m3u8")
    }
    
    /**
     * Check if HLS files exist for a given video name
     * 
     * @param videoName Name of the video (without extension)
     * @return True if HLS directory and playlist exist
     */
    fun hasHLSFiles(videoName: String): Boolean {
        val hlsDir = getHLSDirectory(videoName)
        val playlist = getPlaylistPath(videoName)
        
        return Files.exists(hlsDir) && Files.isDirectory(hlsDir) && Files.exists(playlist)
    }
    
    /**
     * Extract video name from file path
     * 
     * @param path Video file path
     * @return Video name without extension
     */
    fun extractVideoName(path: Path): String {
        val fileName = path.fileName.toString()
        return fileName.substringBeforeLast(".")
    }
    
    /**
     * Get all HLS segments for a video with timing information
     * 
     * @param videoName Name of the video
     * @return List of HLS segments or empty list if no HLS files found
     */
    fun getHLSSegments(videoName: String): List<HLSSegment> {
        if (!hasHLSFiles(videoName)) {
            return emptyList()
        }
        
        return try {
            parsePlaylist(getPlaylistPath(videoName))
        } catch (e: Exception) {
            emptyList()
        }
    }
}
