export type Media = {
  id: number;
  name: string;
  size_bytes: number;
  boot: {
    profile?: string;
    kernel?: string;
    initrd?: string;
    dtb?: string;
    cmdline?: string;
    managed?: boolean;
  };
  layout: {
    table?: string;
    partitions?: {
      number: number;
      filesystem: string;
      offset: number;
      size_bytes: number;
    }[];
  };
  state: string;
};
export type Peripheral = {
  id: string;
  device_type: string;
  display_name: string;
  connector: string;
  category: string;
  driver: string;
  capabilities: string[];
  limitation: string;
};
export type Status = {
  power: "OFF" | "STARTING" | "RUNNING" | "STOPPING" | "ERROR";
  error: string | null;
  pid: number | null;
  profile: {
    id: string;
    machine: string;
    name: string;
    cpu: string;
    memory_mib: number;
    cores: number;
    limitations: string;
  };
  profiles: {
    id: string;
    name: string;
    supported: boolean;
    limitations: string;
  }[];
  peripherals: Peripheral[];
  media: Media[];
  uart: {
    mode: "disconnected" | "host";
    endpoint: string | null;
    policy: string;
    dropped_bytes: number;
  };
  display: {
    supported: boolean;
    available: boolean;
    viewer_connected: boolean;
    backend: string;
    resolution: string;
    keyboard: string;
    limitation: string;
  };
  network: {
    link: boolean;
    backend: string;
    mac: string;
    guest_ip: string | null;
    ssh: string;
  };
  commands: { uart: string; logs: string };
  events: string[];
  qmp_events: unknown[];
  guest: Record<string, unknown> | null;
  diagnostics: string;
};
export const active = (power: Status["power"]) =>
  ["RUNNING", "STARTING", "STOPPING"].includes(power);
