/** 路由与菜单可见性：admin / energy / ops */
export const ROLES = {
  ADMIN: 'admin',
  ENERGY: 'energy',
  OPS: 'ops',
}

/** 路由 meta.roles：满足其一即可访问 */
export const ROUTE_ROLES = {
  dashboard: [ROLES.ADMIN, ROLES.ENERGY],
  energy: [ROLES.ADMIN, ROLES.ENERGY],
  stats: [ROLES.ADMIN, ROLES.ENERGY],
  benchmark: [ROLES.ADMIN, ROLES.ENERGY],
  knowledge: [ROLES.ADMIN, ROLES.OPS],
  incidents: [ROLES.ADMIN, ROLES.ENERGY, ROLES.OPS],
  twin: [ROLES.ADMIN, ROLES.OPS],
  operations: [ROLES.ADMIN, ROLES.ENERGY],
  pricing: [ROLES.ADMIN, ROLES.ENERGY],
  admin: [ROLES.ADMIN],
  screen: [ROLES.ADMIN, ROLES.ENERGY, ROLES.OPS],
}

export function canAccessRoute(routeName, role) {
  const allowed = ROUTE_ROLES[routeName]
  if (!allowed?.length) return true
  return allowed.includes(role)
}

export function canWriteIncidents(role) {
  return role === ROLES.ADMIN || role === ROLES.OPS
}

export function defaultHomePath(role) {
  if (role === ROLES.OPS) return '/incidents'
  return '/dashboard'
}

export const ROLE_TAG_TYPE = {
  admin: 'danger',
  energy: 'warning',
  ops: 'success',
}
