package dev.dres.api.rest.handler.collection

import dev.dres.api.rest.handler.PostRestHandler
import dev.dres.api.rest.types.collection.ApiBulkImportMediaItemRequest
import dev.dres.api.rest.types.collection.ApiBulkImportResult
import dev.dres.api.rest.types.status.ErrorStatus
import dev.dres.api.rest.types.status.ErrorStatusException
import dev.dres.mgmt.MediaCollectionManager
import io.javalin.http.BadRequestResponse
import io.javalin.http.Context
import io.javalin.openapi.*

/**
 * Handler for bulk importing media items with duplicate detection.
 *
 * @author Generated
 * @version 1.0
 */
class BulkImportMediaItemHandler : AbstractCollectionHandler(), PostRestHandler<ApiBulkImportResult> {

    override val route: String = "mediaItem/bulkImport"

    @OpenApi(
        summary = "Bulk import media items to the specified media collection with duplicate detection.",
        path = "/api/v2/mediaItem/bulkImport",
        methods = [HttpMethod.POST],
        operationId = OpenApiOperation.AUTO_GENERATE,
        tags = ["Collection"],
        requestBody = OpenApiRequestBody([OpenApiContent(ApiBulkImportMediaItemRequest::class)]),
        responses = [
            OpenApiResponse("200", [OpenApiContent(ApiBulkImportResult::class)]),
            OpenApiResponse("400", [OpenApiContent(ErrorStatus::class)]),
            OpenApiResponse("404", [OpenApiContent(ErrorStatus::class)]),
            OpenApiResponse("500", [OpenApiContent(ErrorStatus::class)])
        ]
    )
    override fun doPost(ctx: Context): ApiBulkImportResult {
        
        /* Parse bulk import request and perform sanity checks */
        val request = try {
            ctx.bodyAsClass(ApiBulkImportMediaItemRequest::class.java)
        } catch (e: BadRequestResponse) {
            throw ErrorStatusException(400, "Invalid request body: ${e.message}", ctx)
        } catch (e: IllegalArgumentException) {
            throw ErrorStatusException(400, e.message ?: "Invalid parameters", ctx)
        }

        // Statistics tracking
        val totalItems = request.videoItems.size
        val importedItems = mutableListOf<String>()
        val skippedItems = mutableListOf<String>()
        val errorItems = mutableListOf<String>()

        // Process each video item using MediaCollectionManager
        for (videoItem in request.videoItems) {
            try {
                MediaCollectionManager.addMediaItem(videoItem)
                importedItems.add(videoItem.name)
                
            } catch (e: IllegalArgumentException) {
                // MediaCollectionManager throws IllegalArgumentException for duplicates
                if (e.message?.contains("already exists") == true) {
                    skippedItems.add(videoItem.name)
                } else {
                    errorItems.add(videoItem.name)
                }
            } catch (e: Exception) {
                errorItems.add(videoItem.name)
            }
        }

        return ApiBulkImportResult(
            success = errorItems.isEmpty(),
            totalItems = totalItems,
            importedItems = importedItems.size,
            skippedItems = skippedItems.size,
            errorItems = errorItems.size,
            message = "Bulk import completed: ${importedItems.size} imported, ${skippedItems.size} skipped, ${errorItems.size} errors",
            skippedItemNames = skippedItems,
            errorItemNames = errorItems
        )
    }
}