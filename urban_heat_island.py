// Urban Heat Island Detection using Landsat 8 Imagery in Google Earth Engine

// 1. Load the FAO Admin Boundaries to define your Region of Interest (ROI)
var adminRegions = ee.FeatureCollection("FAO/GAUL/2015/level1");
Map.addLayer(adminRegions, {}, 'Global Admin Boundary', false);

// 2. Define a central coordinate (a point in the city of interest)
var centralCoord = [80.2707, 13.0827];
var cityPoint = ee.Geometry.Point(centralCoord);

// 3. Filter the admin layer using the city point to extract the boundary
var analysisBoundary = adminRegions.filterBounds(cityPoint)
  .map(function(feature) {
    return feature.simplify(1000); // simplifies geometry to reduce complexity
  });

Map.centerObject(analysisBoundary);
Map.addLayer(analysisBoundary, {}, 'ROI');

// 4. Define analysis period 
var startDate = '2023';
var endDate = '2024';

// 5. Load Dynamic World classification to extract only urban pixels (class 6)
var dynamicUrban = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
  .select('label')
  .filterDate(startDate, endDate)
  .filterBounds(analysisBoundary)
  .filter(ee.Filter.calendarRange(5, 9, 'month')) // Focus on summer months
  .mode()
  .eq(6); // Class 6 corresponds to "Built Area"

Map.addLayer(dynamicUrban.clip(analysisBoundary), {}, 'Urban Mask', false);

// Import Landsat 8  and Visualize Metadata
var landsat8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
  .select('ST_B10')
  .filterBounds(analysisBoundary)
  .filterDate(startDate, endDate)
  .filter(ee.Filter.lt('CLOUD_COVER', 10))
  print('Metadata_LS_8', landsat8);

// 6. Load Landsat 8 Thermal Band and apply scaling to get temperature in Kelvin
var landsatThermal = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
  .select('ST_B10')
  .filterBounds(analysisBoundary)
  .filterDate(startDate, endDate)
  .filter(ee.Filter.lt('CLOUD_COVER', 10))
  .map(function(image) {
    var scaleFactor = ee.Number(image.get('TEMPERATURE_MULT_BAND_ST_B10'));
    var offsetFactor = ee.Number(image.get('TEMPERATURE_ADD_BAND_ST_B10'));
    var brightnessTemp = image.multiply(scaleFactor).add(offsetFactor);
    return brightnessTemp.copyProperties(image, image.propertyNames());
  });

// 7. Take median composite of temperature images
var medianThermal = landsatThermal.median();
Map.addLayer(medianThermal.clip(analysisBoundary), {}, 'Median LST (Kelvin)', false);

// 8. Compute mean Land Surface Temperature (LST) across ROI
var meanLST = ee.Number(
  medianThermal.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: analysisBoundary,
    scale: 100,
    maxPixels: 1e13
  }).values().get(0)
);
print('Mean LST (in Kelvin):', meanLST);

// 9. Calculate Urban Heat Island Index as a relative deviation from mean
var uhiIndex = medianThermal.expression(
  '(TIR - MEAN) / MEAN',
  {
    'TIR': medianThermal,
    'MEAN': meanLST
  }
).rename('UHI_Index');

// Better visualization with clear colors
// 10. Classify UHI Intensity into 5 categories
var uhiClasses = ee.Image.constant(0)
  .where(uhiIndex.gte(0).and(uhiIndex.lt(0.005)), 1)   // Mild
  .where(uhiIndex.gte(0.005).and(uhiIndex.lt(0.010)), 2) // Moderate
  .where(uhiIndex.gte(0.010).and(uhiIndex.lt(0.015)), 3) // Strong
  .where(uhiIndex.gte(0.015).and(uhiIndex.lt(0.020)), 4) // Very Strong
  .where(uhiIndex.gte(0.020), 5) // Extreme
  .updateMask(dynamicUrban);

// 11. Visualize UHI Classes with colors
Map.addLayer(uhiClasses.clip(analysisBoundary), {min: 1, max: 5, palette: ['white', 'yellow', 'orange', 'red', 'darkred']}, 'UHI Classes', true);

// 12. Export UHI classified layer to Google Drive
Export.image.toDrive({
  image: uhiClasses.clip(analysisBoundary),
  description: 'UHI_Classes_Landsat8_Export',
  folder: 'UrbanHeat',
  region: analysisBoundary,
  scale: 100,
  crs: 'EPSG:4326',
  maxPixels: 1e13
});
