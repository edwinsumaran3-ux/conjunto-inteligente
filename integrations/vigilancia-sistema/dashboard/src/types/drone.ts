export interface DroneModel {
  key: string;
  vendor: string;
  model: string;
  category: "multirotor" | "vtol-hibrido" | "ala-fija-vtol" | "tethered";
  tethered: boolean;
  max_flight_time_min: number | null;
  max_altitude_m: number | null;
  detection_range_km: number | null;
  typical_use: string[];
}
