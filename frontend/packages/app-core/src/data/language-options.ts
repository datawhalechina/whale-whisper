export type LanguageId = "zh-CN" | "en";

export type LanguageOption = {
  id: LanguageId;
  label: string;
  description?: string;
};

export const languageOptions: LanguageOption[] = [
  { id: "zh-CN", label: "中文", description: "简体中文" },
  { id: "en", label: "English", description: "English" },
];
