import machineProfiles from "../../espresso_mcp/machine_profiles.json";
import grinderProfiles from "../../espresso_mcp/grinder_profiles.json";

type NamedProfile = {
  machine_name?: string;
  grinder_name?: string;
};

type MachineProfile = {
  machine_name: string;
  aliases?: string[];
  specs?: {
    has_built_in_grinder?: boolean;
  };
  grind_adjustment_notes?: string;
};

export type GrinderProfile = {
  grinder_name: string;
  aliases?: string[];
  setting_type?: "numeric_integer" | "numeric_decimal";
  small_step?: number;
  min_setting?: number | null;
  max_setting?: number | null;
  espresso_range?: [number, number] | null;
  notes?: string;
};

export const machineProfileOptions = (machineProfiles as MachineProfile[])
  .filter((profile) => profile.machine_name !== "Generic Espresso Machine")
  .sort((left, right) => left.machine_name.localeCompare(right.machine_name, undefined, { sensitivity: "base" }));

export const machineOptions = sortedNames(
  (machineProfiles as NamedProfile[]).map((profile) => profile.machine_name),
  "Generic Espresso Machine"
);

export function getMachineProfile(machineName: string): MachineProfile | null {
  const query = normalize(machineName);
  if (!query) {
    return null;
  }

  return (
    machineProfileOptions.find((profile) => {
      const names = [profile.machine_name, ...(profile.aliases ?? [])];
      return names.some((name) => normalize(name) === query);
    }) ?? null
  );
}

export function machineSupportsBuiltInGrinder(machineName: string) {
  const query = normalize(machineName);
  if (!query) {
    return false;
  }

  const profile = getMachineProfile(machineName);
  if (!profile) {
    return true;
  }

  return machineHasKnownBuiltInGrinder(machineName);
}

export function machineHasKnownBuiltInGrinder(machineName: string) {
  const profile = getMachineProfile(machineName);
  if (!profile) {
    return false;
  }

  const notes = profile.grind_adjustment_notes?.toLowerCase() ?? "";
  return Boolean(profile.specs?.has_built_in_grinder) || ((notes.includes("built-in") || notes.includes("built in")) && notes.includes("grinder"));
}

export const grinderProfileOptions = (grinderProfiles as GrinderProfile[])
  .filter((profile) => profile.grinder_name !== "Generic Numeric Grinder")
  .sort((left, right) => left.grinder_name.localeCompare(right.grinder_name, undefined, { sensitivity: "base" }));

export const grinderOptions = grinderProfileOptions.map((profile) => profile.grinder_name);

export function getGrinderProfile(grinderName: string): GrinderProfile | null {
  const query = normalize(grinderName);
  if (!query) {
    return null;
  }

  return (
    grinderProfileOptions.find((profile) => {
      const names = [profile.grinder_name, ...(profile.aliases ?? [])];
      return names.some((name) => normalize(name) === query);
    }) ?? null
  );
}

export function grindSettingOptions(profile: GrinderProfile | null) {
  if (!profile) {
    return [];
  }

  const min = profile.min_setting;
  const max = profile.max_setting;
  const step = grindSettingStep(profile);
  if (typeof min !== "number" || typeof max !== "number" || !step || max < min) {
    return [];
  }

  const optionCount = Math.floor((max - min) / step) + 1;
  if (optionCount > 90) {
    return [];
  }

  return Array.from({ length: optionCount }, (_, index) => formatSetting(min + index * step, profile));
}

export function grindSettingStep(profile: GrinderProfile | null) {
  if (!profile) {
    return undefined;
  }

  if (profile.setting_type === "numeric_integer") {
    return 1;
  }

  return profile.small_step ?? 0.1;
}

export function validateGrindSetting(value: string, profile: GrinderProfile | null) {
  if (!value.trim()) {
    return "Enter the current grind setting.";
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "Use a numeric grind setting so the next setting can be calculated.";
  }

  if (!profile) {
    return "";
  }

  if (profile.setting_type === "numeric_integer" && !Number.isInteger(parsed)) {
    return `${profile.grinder_name} accepts whole-number grind settings.`;
  }

  if (typeof profile.min_setting === "number" && parsed < profile.min_setting) {
    return `${profile.grinder_name} accepts settings from ${formatSetting(profile.min_setting, profile)} to ${formatSetting(profile.max_setting, profile)}.`;
  }

  if (typeof profile.max_setting === "number" && parsed > profile.max_setting) {
    return `${profile.grinder_name} accepts settings from ${formatSetting(profile.min_setting, profile)} to ${formatSetting(profile.max_setting, profile)}.`;
  }

  return "";
}

export function grindSettingHint(profile: GrinderProfile | null) {
  if (!profile) {
    return "Numeric setting; unknown grinder will use the generic profile.";
  }

  const min = profile.min_setting;
  const max = profile.max_setting;
  const step = grindSettingStep(profile);
  const range = typeof min === "number" && typeof max === "number" ? `${formatSetting(min, profile)}-${formatSetting(max, profile)}` : "numeric";
  const espressoRange = profile.espresso_range ? ` Espresso often starts around ${profile.espresso_range[0]}-${profile.espresso_range[1]}.` : "";
  const stepText = step ? ` Step ${step}.` : "";
  return `${profile.grinder_name}: ${range}.${stepText}${espressoRange}`;
}

function sortedNames(values: Array<string | undefined>, fallbackName: string) {
  return values
    .filter((value): value is string => Boolean(value) && value !== fallbackName)
    .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));
}

function formatSetting(value: number | null | undefined, profile: GrinderProfile) {
  if (typeof value !== "number") {
    return "";
  }

  if (profile.setting_type === "numeric_integer") {
    return String(Math.round(value));
  }

  return String(Math.round(value * 100) / 100);
}

function normalize(value: string) {
  return value.toLowerCase().replaceAll("-", " ").replace(/\s+/g, " ").trim();
}
