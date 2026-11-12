# Bundled CTA route geometry fallback

`cta_bus_routes.geojson` is a static GeoJSON export of the Cook County public
transit service's **CTA Bus Route** layer (129 route features). It was retrieved
on 2026-11-12 for use only when the City of Chicago route dataset is
unreachable. The original download endpoint is:

<https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/1/query?where=1%3D1&outFields=*&outSR=4326&f=geojson>

Layer metadata and attribution:

<https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/layers>

These are static route paths, not live bus positions. The live vehicle layer
uses the separate CTA Bus Tracker API.
