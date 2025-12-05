# Testing Queries

2025-11-10 (v1)

## Access and Coverage

1. How many people lives within a 800-meter radius of a park?
   - **Related data:** `parks`, `popemploy`
   - **Geoprocessing steps:**
     1. Generate an 800-meter buffer for each polygon in the `parks` data
     2. Select polygons in `popemploy` data that intersect with the park buffers or park polygons
     3. Sum the population count within the selected `popemploy` polygons

2. What is the park acres per 1,000 residents (by block group)?
   - **Related data:** `parks`, `equity`
   - **Geoprocessing steps:**
     1. Perform a spatial join between `parks` and `equity` (block group polygons) to calculate total park area per block group, the join condition is that polygons of parks are intersect with polygons of equity data
     2. Calculate the total acres of parks within each block group
     3. Divide park acres by (population / 1,000) for each block group to get park acres per 1,000 residents

3. Which regional activity centers (RACs) lack a transit stop within 400 m?
   - **Related data:** `regional_activity_centers`, `transit_stops`
   - **Geoprocessing steps:**
     1. Generate a 400-meter buffer for each point in the `transit_stops` data
     2. Perform a spatial query to identify `regional_activity_centers` polygons that do NOT intersect with any transit stop buffers
     3. Return the list of RACs without nearby transit access

## Safety

1. Which schools are within 150 m of high-traffic roads (e.g., AADT ≥ 25k)?
   - **Related data:** `schools`, `roads`
   - **Geoprocessing steps:**
     1. Filter `roads` data to select only road segments where AADT ≥ 25,000
     2. Generate a 150-meter buffer for each filtered high-traffic road segment
     3. Select `schools` points that intersect with the road buffers
     4. Return the list of schools within 150m of high-traffic roads

2. Which block group (in `equity` table) have the highest cumulative nearby traffic?
   - **Related data:** `equity`, `roads`
   - **Geoprocessing steps:**
     1. Perform a spatial join between `equity` block groups and `roads` (join condition is that for each block group, join roads that intersect with the block group or within a certain distance with the block group, e.g., 100 meters)
     2. For each block group, sum the AADT values of all joined road segments
     3. Sort block groups by cumulative AADT in descending order
     4. Return the block groups with the highest cumulative traffic

## Demand

1. Which road segments traverse the highest-employment TAZs?
   - **Related data:** `roads`, `popemploy`
   - **Geoprocessing steps:**
     1. Perform a spatial join between `roads` and `popemploy` TAZ polygons (join condition is that for each segment of roads, join TAZs that intersect with the road segment)
     2. Assign employment values from `popemploy` to each joined road segment
     3. Sort road segments by the employment count of their joined TAZ in descending order
     4. Return the road segments traversing the highest-employment areas

2. What is the transit stop density (stops per acre) for each RAC?
   - **Related data:** `transit_stops`, `regional_activity_centers`
   - **Geoprocessing steps:**
     1. Perform a spatial join (point-in-polygon) to count the number of `transit_stops` within each `regional_activity_centers` polygon
     2. Calculate the area (in acres) of each RAC polygon
     3. Divide the count of transit stops by the area to get density (stops per acre)
     4. Return the transit stop density for each RAC

## Equity

1. Which high-equity-need areas (income/minority-based) lack park access (within 1 mile)?
   - **Related data:** `equity`, `parks`
   - **Geoprocessing steps:**
     1. Filter `equity` block groups to identify high-equity-need areas based on income and minority criteria
     2. Generate a 1-mile buffer for each polygon in the `parks` data
     3. Select high-need block groups from `equity` that do NOT intersect with any park buffers
     4. Return the list of high-need areas lacking park access

2. What share of high-need residents are within 400 m of transit stops?
   - **Related data:** `equity`, `transit_stops`
   - **Geoprocessing steps:**
     1. Filter `equity` block groups to identify high-need areas
     2. Generate a 400-meter buffer for each point in the `transit_stops` data
     3. Intersect `equity` block groups with transit stop buffers to identify block groups with transit access
     4. Sum the population within intersecting block groups and divide by total high-need population to calculate the percentage
     5. Return the share/percentage of high-need residents with transit access

3. Which corridors have high traffic (AADT), high-need equity scores, but few transit stops?
   - **Related data:** `roads`, `equity`, `transit_stops`
   - **Geoprocessing steps:**
     1. Filter `roads` to select segments with high AADT (e.g., AADT ≥ 25,000)
     2. Perform a spatial join between filtered roads and `equity` to identify roads in high-need areas
     3. Generate a buffer around each road segment (e.g., 400 meters)
     4. Count the number of `transit_stops` within each road buffer
     5. Filter roads with low transit stop counts (which can be pre-determined)
     6. Return corridors meeting all three criteria (high traffic, high need, low transit)

## Land Use / Siting

1. Which RACs are best suited for new schools (high population, high jobs, sufficient transit)?
   - **Related data:** `regional_activity_centers`, `popemploy`, `transit_stops`
   - **Geoprocessing steps:**
     1. Perform a spatial join between `regional_activity_centers` and `popemploy` TAZ polygons
     2. Calculate total population and employment counts for each RAC (sum values from intersecting TAZs)
     3. Perform a point-in-polygon join to count the number of `transit_stops` within each RAC
     4. Filter and rank RACs based on criteria: high population, high employment, and sufficient transit stops. Thresholds of filtering can be pre-determined.
     5. Return the top-ranked RACs suitable for new school siting

2. Which TAZ (in `popemploy` table) needs a new RAC (high Pop and/or job density)?
   - **Related data:** `popemploy`, `regional_activity_centers`
   - **Geoprocessing steps:**
     1. Calculate the area of each TAZ polygon in `popemploy`
     2. Calculate population density (population / area) and job density (employment / area) for each TAZ
     3. Perform a spatial query to identify TAZs that do NOT intersect with existing `regional_activity_centers`
     4. Filter TAZs by high density thresholds (high population and/or employment density, which can be pre-determined)
     5. Rank TAZs by density scores and return candidates that need a new RAC
