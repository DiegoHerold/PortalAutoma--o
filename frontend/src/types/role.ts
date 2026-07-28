export type Role = {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  permissions?: string[];
};
