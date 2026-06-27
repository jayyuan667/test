export interface User {
  id: number
  username: string
  role: 'super_admin' | 'enterprise_admin' | 'user'
  enterprise_id: number | null
  enterprise_name: string | null
  is_active: boolean
  created_at: string
  grant_expires_at?: string | null
  quota?: {
    total_granted: number
    used: number
    remaining: number
  }
}

export type UserRole = User['role']

export const UNASSIGNED_ENTERPRISE_LABEL = '未分配企业'

export function isUnassignedUser(user: Pick<User, 'role' | 'enterprise_id'> | null | undefined): boolean {
  return user?.role === 'user' && user.enterprise_id == null
}

export interface Enterprise {
  id: number
  name: string
  is_active: boolean
  created_at: string
  user_count?: number
}

export interface QuotaInfo {
  user_id: number
  username: string
  role: string
  total_granted: number
  used: number
  remaining: number
}

export interface AdminUser extends User {
  quota_total: number
  quota_used: number
}
