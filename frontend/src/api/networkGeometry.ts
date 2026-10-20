import type { NetworkGeometry } from './types';

export interface DisplayNetworkGeometry extends NetworkGeometry {
  coordinate_system: 'geographic';
  source_coordinate_system: 'geographic' | 'schematic';
  bounds: {
    min_lon: number;
    max_lon: number;
    min_lat: number;
    max_lat: number;
  } | null;
  buses: Record<string, NetworkGeometry['buses'][string] & { lat: number; lon: number }>;
  transformers: Array<NetworkGeometry['transformers'][number] & { lat: number; lon: number }>;
}

export function toDisplayNetworkGeometry(
  geometry: NetworkGeometry | null,
  anchor: { latitude: number; longitude: number },
): DisplayNetworkGeometry | null {
  if (!geometry) return null;

  if (geometry.coordinate_system === 'geographic') {
    const buses = Object.fromEntries(Object.entries(geometry.buses).flatMap(([name, bus]) => (
      bus.lat === undefined || bus.lon === undefined ? [] : [[name, { ...bus, lat: bus.lat, lon: bus.lon }]]
    )));
    const transformers = geometry.transformers.flatMap((transformer) => (
      transformer.lat === undefined || transformer.lon === undefined
        ? []
        : [{ ...transformer, lat: transformer.lat, lon: transformer.lon }]
    ));
    const bounds = geometry.bounds;
    return {
      ...geometry,
      coordinate_system: 'geographic',
      source_coordinate_system: 'geographic',
      buses,
      transformers,
      bounds: bounds && bounds.min_lon !== undefined && bounds.max_lon !== undefined
        && bounds.min_lat !== undefined && bounds.max_lat !== undefined
        ? { min_lon: bounds.min_lon, max_lon: bounds.max_lon, min_lat: bounds.min_lat, max_lat: bounds.max_lat }
        : null,
    };
  }

  const bounds = geometry.bounds;
  if (!bounds || bounds.min_x === undefined || bounds.max_x === undefined
    || bounds.min_y === undefined || bounds.max_y === undefined) return null;

  const centerX = (bounds.min_x + bounds.max_x) / 2;
  const centerY = (bounds.min_y + bounds.max_y) / 2;
  const latitudeDegreesPerUnit = 100 / 111_320;
  const longitudeDegreesPerUnit = latitudeDegreesPerUnit / Math.max(Math.cos(anchor.latitude * Math.PI / 180), 0.01);
  const project = ([x, y]: [number, number]): [number, number] => [
    anchor.longitude + (x - centerX) * longitudeDegreesPerUnit,
    anchor.latitude + (y - centerY) * latitudeDegreesPerUnit,
  ];
  const buses = Object.fromEntries(Object.entries(geometry.buses).map(([name, bus]) => {
    const [lon, lat] = project([bus.x, bus.y]);
    return [name, { ...bus, lon, lat }];
  }));
  const lines = geometry.lines.map((line) => ({
    ...line,
    coordinates: line.coordinates.map((coordinate) => project(coordinate)),
  }));
  const transformers = geometry.transformers.map((transformer) => {
    const [lon, lat] = project([transformer.x, transformer.y]);
    return { ...transformer, lon, lat };
  });
  const allCoordinates = [
    ...Object.values(buses).map((bus) => [bus.lon, bus.lat] as [number, number]),
    ...lines.flatMap((line) => line.coordinates),
  ];

  return {
    ...geometry,
    coordinate_system: 'geographic',
    source_coordinate_system: 'schematic',
    buses,
    lines,
    transformers,
    bounds: allCoordinates.length ? {
      min_lon: Math.min(...allCoordinates.map(([lon]) => lon)),
      max_lon: Math.max(...allCoordinates.map(([lon]) => lon)),
      min_lat: Math.min(...allCoordinates.map(([, lat]) => lat)),
      max_lat: Math.max(...allCoordinates.map(([, lat]) => lat)),
    } : null,
  };
}