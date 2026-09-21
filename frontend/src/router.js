import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  { path: '/pda-scan', component: () => import('./views/PdaScan.vue'), meta: { title: '设备领用归还' } },
  {
    path: '/',
    component: () => import('./views/Layout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '工作台' } },
      { path: 'assets', component: () => import('./views/AssetList.vue'), meta: { title: '资产台账' } },
      { path: 'assets/:id', component: () => import('./views/AssetDetail.vue'), meta: { title: '资产详情' } },
      { path: 'assets-import', component: () => import('./views/AssetImport.vue'), meta: { title: '批量导入' } },
      { path: 'categories', component: () => import('./views/Categories.vue'), meta: { title: '类别管理' } },
      { path: 'repairs', component: () => import('./views/Repairs.vue'), meta: { title: '维修管理' } },
      { path: 'flows', component: () => import('./views/Flows.vue'), meta: { title: '资产流程' } },
      { path: 'stocktakes', component: () => import('./views/Stocktakes.vue'), meta: { title: '资产盘点' } },
      { path: 'economy', component: () => import('./views/Economy.vue'), meta: { title: '报废预测' } },
      { path: 'unassigned-dept', component: () => import('./views/UnassignedDept.vue'), meta: { title: '未分配部门' } },
      { path: 'pda', component: () => import('./views/PdaLocation.vue'), meta: { title: '移动设备定位' } },
{ path: 'pda-bigscreen', component: () => import('./views/PdaBigScreen.vue'), meta: { title: '定位大屏' } },
    ],
  },
  { path: '/bigscreen', component: () => import('./views/BigScreen.vue') },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to, from, next) => {
  if (to.path !== '/login' && to.path !== '/bigscreen' && to.path !== '/pda-scan' && !localStorage.getItem('token')) return next('/login')
  next()
})

export default router
