# geomas
A multi-agent system for geospatial data processing and analytics.

## Prerequisites

### Google Cloud SDK (gcloud CLI) - Only Required for Database Modifications

**Note**: You only need to install `gcloud` if you want to modify or update the
database with new GIS data. If you're just using the pre-seeded database, you
can skip this section.

The database loads vector and raster data from Google Cloud Storage using the
`gcloud` command-line tool. To modify the database, you'll need:

**Install Google Cloud SDK:**
- Visit [Google Cloud SDK installation page](
    https://cloud.google.com/sdk/docs/install)
- Download and install `GoogleCloudSDKInstaller.exe`
- Restart your terminal/PowerShell after installation
- Verify: `gcloud --version`

**Note**: The `gcloud` CLI uses its own bundled Python environment, so you
don't need to install Python dependencies in your project's virtual
environment for gcloud commands.

For detailed instructions on modifying the database and uploading new data,
see `db/README.md`.

## GIS Data
The following tables are pre-seeded into the database:

| id | name | original file | geometry type | extent | notes |
|----|------|---------------|---------------|--------|-------|
| 1 | parks | parks.shp | polygon | state | |
| 2 | schools | schools.shp | point | broward county | |
| 3 | roads | roads.shp | line | broward county | road segments and AADT |
| 4 | popemploy | popemploy.shp | polygon | broward county | TAZ-level population & employment counts |
| 5 | transit_stops | transit_stops.shp | point | broward county | |
| 6 | regional_activity_centers | rac.shp | polygon | broward county | |
| 7 | equity | equity_2022.shp | polygon | broward county | block group-level equity variables |