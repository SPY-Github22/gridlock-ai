import { create } from 'zustand';

export interface EventData {
  id: number;
  lat: number;
  lng: number;
  cause: string;
  vehicleType?: string;
  timeHour: number;
}

interface SimulationState {
  isSimulating: boolean;
  setIsSimulating: (val: boolean) => void;
  
  eventCause: string;
  setEventCause: (cause: string) => void;
  
  vehicleType: string;
  setVehicleType: (type: string) => void;
  
  timeOfDayHour: number;
  setTimeOfDayHour: (hour: number) => void;
  
  hoveredEvent: EventData | null;
  setHoveredEvent: (evt: EventData | null) => void;
  
  events: EventData[];
  addEvent: (event: EventData) => void;
  clearEvents: () => void;
  
  riskScore: number | null;
  setRiskScore: (score: number | null) => void;
  
  roadClosureProb: number | null;
  setRoadClosureProb: (prob: number | null) => void;
  
  actions: any[];
  setActions: (actions: any[]) => void;
  
  etrMinutes: number | null;
  setEtrMinutes: (mins: number | null) => void;
  
  detourPossible: boolean | null;
  setDetourPossible: (val: boolean | null) => void;
  
  affectedRoads: any | null;
  setAffectedRoads: (roads: any | null) => void;
  
  spilloverRoads: any | null;
  setSpilloverRoads: (roads: any | null) => void;
  
  detourRoutes: any | null;
  setDetourRoutes: (roads: any | null) => void;
  
  reset: () => void;
}

export const useStore = create<SimulationState>((set) => ({
  isSimulating: false,
  setIsSimulating: (val) => set({ isSimulating: val }),
  
  eventCause: 'Accident',
  setEventCause: (cause) => set({ eventCause: cause }),
  
  vehicleType: 'Car/Taxi',
  setVehicleType: (type) => set({ vehicleType: type }),
  
  timeOfDayHour: 8, // Default 8 AM
  setTimeOfDayHour: (hour) => set({ timeOfDayHour: hour }),
  
  hoveredEvent: null,
  setHoveredEvent: (evt) => set({ hoveredEvent: evt }),
  
  events: [],
  addEvent: (evt) => set((state) => ({ events: [...state.events, evt] })),
  clearEvents: () => set({ events: [] }),
  
  riskScore: null,
  setRiskScore: (score) => set({ riskScore: score }),
  
  roadClosureProb: null,
  setRoadClosureProb: (prob) => set({ roadClosureProb: prob }),
  
  actions: [],
  setActions: (actions) => set({ actions }),
  
  etrMinutes: null,
  setEtrMinutes: (mins) => set({ etrMinutes: mins }),
  
  detourPossible: null,
  setDetourPossible: (val) => set({ detourPossible: val }),
  
  affectedRoads: null,
  setAffectedRoads: (roads) => set({ affectedRoads: roads }),
  
  spilloverRoads: null,
  setSpilloverRoads: (roads) => set({ spilloverRoads: roads }),
  
  detourRoutes: null,
  setDetourRoutes: (roads) => set({ detourRoutes: roads }),
  
  reset: () => set({ 
    isSimulating: false, 
    events: [], 
    riskScore: null, 
    roadClosureProb: null, 
    actions: [],
    etrMinutes: null,
    detourPossible: null,
    affectedRoads: null,
    spilloverRoads: null,
    detourRoutes: null
  })
}));
