"""URL routes for catalogue APIs."""

from django.urls import path

from catalog.api.views import (
    CatalogConfigAPIView,
    CatalogIncrementalSyncAPIView,
    ProductScanAPIView,
)

urlpatterns = [
    path(
        "config/",
        CatalogConfigAPIView.as_view(),
        name="catalog-config",
    ),
    path(
        "products/scan/",
        ProductScanAPIView.as_view(),
        name="catalog-product-scan",
    ),
    path(
        "products/incremental/",
        CatalogIncrementalSyncAPIView.as_view(),
        name="catalog-products-incremental",
    ),
]
