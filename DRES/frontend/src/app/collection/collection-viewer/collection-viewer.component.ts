import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog, MatDialogConfig } from '@angular/material/dialog';
import {BehaviorSubject, mergeMap, Observable, of, Subject, Subscription} from 'rxjs';
import { catchError, filter, map, retry, shareReplay, switchMap } from 'rxjs/operators';
import { AppConfig } from '../../app.config';
import {
  MediaItemBuilderData,
  MediaItemBuilderDialogComponent,
} from '../collection-builder/media-item-builder-dialog/media-item-builder-dialog.component';
import { MatPaginator } from '@angular/material/paginator';
import { MatTableDataSource } from '@angular/material/table';
import { MatSort } from '@angular/material/sort';
import {ApiMediaItem, ApiPopulatedMediaCollection, CollectionService} from '../../../../openapi';

@Component({
  selector: 'app-collection-viewer',
  templateUrl: './collection-viewer.component.html',
  styleUrls: ['./collection-viewer.component.scss'],
})
export class CollectionViewerComponent implements AfterViewInit, OnDestroy {

  public isLoading = true;

  displayedColumns = ['actions', 'id', 'name', 'location', 'type', 'durationMs', 'fps'];

  /** Material Table UI element for sorting. */
  @ViewChild(MatSort) sort: MatSort;

  /** Material Table UI element for pagination. */
  @ViewChild('paginator') paginator: MatPaginator;

  /** File input element for JSON import. */
  @ViewChild('fileInput') fileInput: ElementRef<HTMLInputElement>;

  /** Data source for Material tabl.e */
  dataSource = new MatTableDataSource<ApiMediaItem>();

  /** Observable containing the collection ID of the collection displayed by this component. Derived from active route. */
  collectionId: Observable<string>;

  /** Observable containing the media collection information. */
  collection: Observable<ApiPopulatedMediaCollection>;

  /** A subject used to trigger refrehs of the list. */
  refreshSubject: Subject<void> = new BehaviorSubject(null);

  /** Reference to the subscription held by this component. */
  private subscription: Subscription;

  constructor(
    private collectionService: CollectionService,
    private activeRoute: ActivatedRoute,
    private snackBar: MatSnackBar,
    private router: Router,
    private dialog: MatDialog,
    private config: AppConfig
  ) {
    this.collectionId = this.activeRoute.params.pipe(map((p) => p.collectionId));
  }

  /**
   * Register subscription for submission data;
   *
   * TODO: In this implementation, pagination is done on the client side!
   */
  ngAfterViewInit(): void {
    /* Initialize sorting and pagination. */
    this.dataSource.paginator = this.paginator;
    this.dataSource.sort = this.sort;
    /* Custom filter: on ID, Name and Location */
    this.dataSource.filterPredicate = (data: ApiMediaItem, value: string) => data.mediaItemId.includes(value) || data.name.includes(value) || data.location.includes(value)

    /*
     * Initialize subscription for collection data.
     *
     * IMPORTANT: Unsubscribe OnDestroy!
     */
    this.collection = this.refreshSubject.pipe(
      mergeMap((s) => this.collectionId),
      switchMap((id) =>
        this.collectionService.getApiV2CollectionByCollectionId(id).pipe(
          retry(3),
          catchError((err, o) => {
            console.log(`[CollectionViewer.${id}] There was an error while loading the current collection ${err?.message}`);
            this.snackBar.open(`There was an error while loading the current collection ${err?.message}`, null, {
              duration: 5000,
            });
            return of(null);
          }),
          filter((q) => q != null)
        )
      ),
      shareReplay({ bufferSize: 1, refCount: true })
    );
    this.subscription = this.collection.subscribe((s: ApiPopulatedMediaCollection) => {
      this.dataSource.data = s.items;
      this.isLoading = false;
    });
  }

  applyFilter(event: Event){
    const filterValue = (event.target as HTMLInputElement).value;
    this.dataSource.filter = filterValue.trim().toLowerCase();

    if(this.dataSource.paginator){
      this.dataSource.paginator.firstPage();
    }
  }

  /**
   * House keeping; clean up subscriptions.
   */
  ngOnDestroy(): void {
    this.subscription.unsubscribe();
    this.subscription = null;
  }

  delete(id: string) {
    if (confirm(`Do you really want to delete media item with ID ${id}?`)) {
      this.collectionService.deleteApiV2MediaItemByMediaId(id).subscribe({
        next: (r) => {
          this.refreshSubject.next();
          this.snackBar.open(`Success: ${r.description}`, null, {duration: 5000});
        },
        error: (r) => {
          this.snackBar.open(`Error: ${r.error.description}`, null, {duration: 5000});
        }
      });
    }
  }

  edit(id: string) {
    this.create(id);
  }

  show(id: string) {
    this.collectionId.subscribe((collectionId) => {
      window.open(this.mediaUrlForItem(id), '_blank');
    });
  }

  create(id?: string) {
    this.collectionId.subscribe((colId: string) => {
      const config = { width: '500px' } as MatDialogConfig<Partial<MediaItemBuilderData>>;
      if (id) {
        config.data = { item: this.dataSource.data.find((it) => it.mediaItemId === id), collectionId: colId } as MediaItemBuilderData;
      } else {
        config.data = { collectionId: colId } as Partial<MediaItemBuilderData>;
      }
      const dialogRef = this.dialog.open(MediaItemBuilderDialogComponent, config);
      dialogRef
        .afterClosed()
        .pipe(
          filter((r) => r != null),
          mergeMap((r: ApiMediaItem) => {
            if (id) {
              return this.collectionService.patchApiV2Mediaitem(r);
            } else {
              return this.collectionService.postApiV2MediaItem(r);
            }
          })
        )
        .subscribe({
          next: (r) => {
            this.refreshSubject.next();
            this.snackBar.open(`Success: ${r.description}`, null, {duration: 5000});
          },
          error: (r) => {
            this.snackBar.open(`Error: ${r.error.description}`, null, {duration: 5000});
          }
        });
    });
  }

  resolveMediaItemById(_: number, item: ApiMediaItem) {
    return item.mediaItemId;
  }

  /**
   * Triggers file input for JSON import
   */
  importFromJson() {
    this.fileInput.nativeElement.click();
  }

  /**
   * Handles file selection for JSON import
   */
  onFileSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) {
      return;
    }

    if (file.type !== 'application/json') {
      this.snackBar.open('Error: Please select a JSON file', null, { duration: 5000 });
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const jsonData = JSON.parse(e.target?.result as string);
        this.processJsonImport(jsonData);
      } catch (error) {
        this.snackBar.open('Error: Invalid JSON file format', null, { duration: 5000 });
      }
    };
    reader.readAsText(file);
  }

  /**
   * Processes the imported JSON data
   */
  private processJsonImport(jsonData: any) {
    this.collectionId.subscribe((colId: string) => {
      if (!jsonData.video_items || !Array.isArray(jsonData.video_items)) {
        this.snackBar.open('Error: JSON must contain "video_items" array', null, { duration: 5000 });
        return;
      }

      const mediaItems = jsonData.video_items.map((item: any) => ({
        name: item.name,
        type: item.type || 'VIDEO',
        collectionId: colId,
        location: item.location,
        durationMs: item.durationMs,
        fps: item.fps,
        metadata: []
      }));

      // Call backend bulk import API
      this.bulkImportMediaItems(colId, mediaItems);
    });
  }

  /**
   * Calls backend bulk import API
   */
  private bulkImportMediaItems(collectionId: string, mediaItems: any[]) {
    this.isLoading = true;
    
    const bulkImportRequest = {
      collectionId: collectionId,
      videoItems: mediaItems
    };

    // Call the new bulk import API endpoint
    fetch('/api/v2/mediaItem/bulkImport', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(bulkImportRequest)
    })
    .then(response => response.json())
    .then(result => {
      this.handleBulkImportResult(result);
    })
    .catch(error => {
      this.isLoading = false;
      this.snackBar.open(`Import failed: ${error.message}`, null, { duration: 8000 });
      console.error('Bulk import error:', error);
    });
  }

  /**
   * Handles bulk import result
   */
  private handleBulkImportResult(result: any) {
    this.isLoading = false;
    this.refreshSubject.next();
    
    let message = `Import completed: ${result.importedItems} imported`;
    if (result.skippedItems > 0) {
      message += `, ${result.skippedItems} skipped (duplicates)`;
    }
    if (result.errorItems > 0) {
      message += `, ${result.errorItems} errors`;
    }
    
    const duration = result.errorItems > 0 ? 10000 : 6000;
    this.snackBar.open(message, null, { duration });

    // Reset file input
    if (this.fileInput) {
      this.fileInput.nativeElement.value = '';
    }
  }

  /**
   * Old method - kept for backward compatibility but not used
   */
  private importMediaItems(collectionId: string, mediaItems: ApiMediaItem[]) {
    // This method is replaced by bulkImportMediaItems
    console.warn('Deprecated method importMediaItems called');
  }

  /**
   * Old method - kept for backward compatibility but not used
   */
  private completeImport(processed: number, errors: number) {
    // This method is replaced by handleBulkImportResult
    console.warn('Deprecated method completeImport called');
  }

  /**
   * Builds the routerLink array for the given id
   */
  private mediaUrlForItem(id: string) {
    const url = this.config.resolveApiUrl(`media/${id}`);
    console.log(url);
    return url;
  }
}
