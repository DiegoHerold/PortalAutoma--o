export type CategoryPermission = {
  category_id: number;
  can_view: boolean;
  can_execute: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_approve: boolean;
};
