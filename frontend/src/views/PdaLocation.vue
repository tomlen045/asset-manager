<template>
  <div>
    <h1 class="page-title">📱 移动设备定位
      <el-tag type="info" size="small" style="margin-left:10px">PDA / 平板 · WiFi 定位</el-tag>
      <el-button style="margin-left:12px" size="small" @click="addOpen = true">➕ 添加设备</el-button>
      <el-button style="margin-left:0" size="small" type="danger" plain @click="openDelete">🗑 删除设备</el-button>
      <el-button style="margin-left:0" size="small" @click="importOpen = true">📥 批量导入</el-button>
      <el-button style="margin-left:0" size="small" @click="openLabels">🏷 二维码标签</el-button>
      <el-button style="margin-left:0" size="small" type="warning" plain @click="$router.push('/pda-bigscreen')">🖥 大屏模式</el-button>
      <el-button style="margin-left:0" size="small" @click="scanOpen = true">📷 扫码登记</el-button>
      <el-button style="margin-left:0" size="small" @click="openGuide">📖 入网指引</el-button>
      <el-button style="margin-left:0" size="small" @click="acOpen = true">🔗 AC 对接</el-button>
      <el-button style="margin-left:0" size="small" @click="openMap">🗺 平面图</el-button>
      <el-button style="margin-left:0" size="small" @click="load" :loading="loading">🔄 刷新</el-button>
    </h1>

        <el-alert v-if="zoneAlarmUnread > 0" type="warning" :closable="false"
              style="margin-bottom:14px" @click="openZoneAlarms">
      <template #title>
        <span style="cursor:pointer">🚨 区域围栏告警：{{ zoneAlarmUnread }} 台终端出现在非允许区域，点击查看</span>
      </template>
    </el-alert>
    <!-- 告警列表对话框 -->
    <el-dialog v-model="alarmOpen" title="🚨 区域围栏告警" width="720px">
      <el-table :data="alarmRows" size="small" max-height="420" border>
        <el-table-column label="设备" min-width="120"><template #default="{row}">{{ row.device_name }}</template></el-table-column>
        <el-table-column label="MAC" width="165"><template #default="{row}">{{ row.mac.toUpperCase() }}</template></el-table-column>
        <el-table-column label="原区域" width="90"><template #default="{row}">{{ row.from_zone || '—' }}</template></el-table-column>
        <el-table-column label="现区域" width="90"><template #default="{row}">
          <span style="color:var(--yellow);font-weight:600">{{ row.to_zone }}</span></template></el-table-column>
        <el-table-column label="接入点" min-width="140"><template #default="{row}">{{ row.ap_name || '—' }}</template></el-table-column>
        <el-table-column label="时间" width="140"><template #default="{row}">{{ row.created_at }}</template></el-table-column>
      </el-table>
      <div style="text-align:right;margin-top:12px">
        <el-button size="small" @click="markAlarmsRead">全部标记已读</el-button>
      </div>
    </el-dialog>

<!-- 汇总卡 -->
    <el-row :gutter="14" style="margin-bottom:14px">
      <el-col :span="6"><div class="stat-card" style="border-top:3px solid var(--accent)">
        <div class="label">设备总数</div>
        <div class="value">{{ sum.total || 0 }}</div>
        <div class="sub">无线终端（NAC 同步）</div></div></el-col>
      <el-col :span="6"><div class="stat-card" style="border-top:3px solid var(--green)">
        <div class="label">🟢 在线</div>
        <div class="value" style="color:var(--green)">{{ sum.online || 0 }}</div>
        <div class="sub">当前在线终端</div></div></el-col>
      <el-col :span="6"><div class="stat-card" style="border-top:3px solid var(--yellow)">
        <div class="label">🔋 低电量</div>
        <div class="value" style="color:var(--yellow)">{{ sum.lowbat || 0 }}</div>
        <div class="sub">电量 ≤ 20%（PDA）</div></div></el-col>
      <el-col :span="6"><div class="stat-card" style="border-top:3px solid var(--red)">
        <div class="label">🔴 失联超3天</div>
        <div class="value" style="color:var(--red)">{{ sum.stale || 0 }}</div>
        <div class="sub">重点找回对象（PDA）</div></div></el-col>
    </el-row>



    <el-row :gutter="14" type="flex" align="stretch">
      <!-- 区域看板 -->
      <el-col :span="8" style="display:flex">
        <el-card style="display:flex;flex-direction:column;width:100%;height:100%">
          <div style="font-weight:600;margin-bottom:10px">🗂️ 组织结构</div>
          <div style="padding:6px 10px;border-radius:6px;margin-bottom:8px;cursor:pointer;border:1px solid var(--border)"
               :style="{background: !q.zone ? 'var(--bg-page)' : ''}"
               @click="q.zone = ''; load()">
            <b>全部</b> <span style="color:var(--text-dim)">({{ sum.total || 0 }})</span>
          </div>
          <div v-if="!sum.zones || !sum.zones.length" style="color:var(--text-dim);font-size:13px">
            暂无数据——同步 AP 清单或设备首次心跳后自动生成区域
          </div>
          <div style="flex:1;overflow-y:auto;min-height:0">
          <div v-for="z in sum.zones" :key="z.zone"
               style="padding:10px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:8px;cursor:pointer"
               :style="{background: q.zone === z.zone ? 'var(--bg-page)' : ''}"
               @click="q.zone = q.zone === z.zone ? '' : z.zone; load()">
            <div style="display:flex;justify-content:space-between;align-items:center">
              <b>{{ z.zone }}</b>
              <span style="font-size:12px">
                <span v-if="z.ap_total">📡 {{ z.ap_online }}/{{ z.ap_total }} AP　</span>
                <span>📱 {{ z.online }}/{{ z.total }} PDA</span>
              </span>
            </div>
            <div style="display:flex;gap:6px;margin-top:6px">
              <el-progress v-if="z.ap_total" :percentage="Math.round(z.ap_online / Math.max(z.ap_total,1) * 100)"
                           :stroke-width="6" :show-text="false" color="#3477f6" style="flex:1" />
              <el-progress :percentage="Math.round(z.online / Math.max(z.total,1) * 100)"
                           :stroke-width="6" :show-text="false"
                           :color="z.online === z.total ? '#12a578' : '#d98f1f'" style="flex:1" />
            </div>
            <div style="font-size:12px;color:var(--text-dim);margin-top:4px">
              <span v-if="z.lowbat">🔋低电量 {{ z.lowbat }}　</span>
              <span v-if="z.stale" style="color:var(--red)">🔴 失联 {{ z.stale }}</span>
            </div>
          
          </div><!-- /zone-scroll --></div>
        </el-card>
      </el-col>

      <!-- 设备清单 -->
      <el-col :span="16" style="display:flex">
        <el-card body-style="display:flex;flex-direction:column;flex:1;overflow:hidden;padding:16px"
                 style="display:flex;flex-direction:column;width:100%;height:100%">
          <div style="display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
            <el-input v-model="q.kw" placeholder="名称/MAC/编号/责任人/AP" style="width:220px"
                      clearable @keyup.enter="load" @clear="load" />
            <el-select v-model="q.state" placeholder="状态" style="width:130px" clearable @change="load">
              <el-option label="🟢 在线" value="online" />
              <el-option label="⚪ 离线" value="offline" />
              <el-option label="🔴 失联≥3天" value="stale" />
              <el-option label="🔋 低电量" value="lowbat" />
            </el-select>
            <el-button @click="load">查询</el-button>
            <div style="flex:1"></div>
            <el-button type="success" plain @click="linkAssets">🔗 自动关联资产</el-button>
            <el-button @click="exportCsv">📤 导出</el-button>
          </div>

          <div style="flex:1;overflow:auto;min-height:200px"><el-table :data="pagedItems" v-loading="loading" stripe border size="small"
                    :row-class-name="rowClass">
            <el-table-column prop="name" label="用户名" min-width="130" show-overflow-tooltip header-align="center" />
            <el-table-column label="MAC地址" width="165" header-align="center">
              <template #default="{row}">{{ row.mac.toUpperCase() }}</template>
            </el-table-column>
            <el-table-column label="终端类型" width="115" header-align="center">
              <template #default="{row}">{{ (row.note || '').split(' · ')[0] || '其他类型' }}</template>
            </el-table-column>
            <el-table-column label="设备名称" width="95" header-align="center">
              <template #default="{row}">—</template>
            </el-table-column>
            <el-table-column label="IP地址" min-width="140" header-align="center">
              <template #default="{row}">{{ row.ip || '—' }}</template>
            </el-table-column>
            <el-table-column prop="zone" label="区域" width="90" header-align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.online ? 'success' : 'info'">{{ row.zone || '未分区' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ap_name" label="接入点" min-width="140" show-overflow-tooltip header-align="center" />
            <el-table-column label="信号" width="80" align="right" header-align="center">
              <template #default="{ row }">{{ row.rssi != null ? row.rssi + 'dBm' : '—' }}</template>
            </el-table-column>
            <el-table-column label="电量" width="80" align="center" header-align="center">
              <template #default="{ row }">
                <span :style="{color: (row.battery != null && row.battery <= 20) ? 'var(--red)' : ''}">
                  {{ row.battery != null ? row.battery + '%' : '—' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90" header-align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="rowTag(row)">{{ rowState(row) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_seen" label="最后心跳" min-width="130" header-align="center" />
            <el-table-column prop="owner" label="责任人" width="90" header-align="center" />
            <el-table-column label="操作" width="195" fixed="right" header-align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="ring(row)"
                           :disabled="!row.online && !row.last_seen">🔔 响铃</el-button>
                <el-button link type="success" size="small" @click="detailOpen(row)">详情</el-button>
                <el-button link type="primary" size="small" @click="editOpen(row)">编辑</el-button>
                <el-button link size="small" @click="showTrack(row)">轨迹</el-button>
                <el-button link size="small" @click="showTrend(row)">趋势</el-button>
              </template>
            </el-table-column>
          </el-table></div>
          <el-pagination style="margin-top:auto;padding-top:14px;justify-content:flex-end"
                         layout="total, prev, pager, next, sizes"
                         :total="items.length" :page-size="pageSize"
                         :current-page="page" :page-sizes="[10, 20, 50, 100]"
                         @current-change="p => page = p"
                         @size-change="s => { pageSize = s; page = 1 }"
                         background small />
        </el-card>
      </el-col>
    </el-row>

            <!-- 在线率报表对话框 -->
    <el-dialog v-model="reportOpen" title="📊 终端在线率报表" width="860px" top="5vh">
      <el-row :gutter="14" v-if="report.zones.length">
        <el-col :span="12">
          <div style="font-weight:600;margin-bottom:8px">各区域在线率</div>
          <div class="rate-row" v-for="z in report.zones" :key="z.zone">
            <span class="rz">{{ z.zone }}</span>
            <div class="rbar"><div class="rbar-in" :style="{width: z.rate + '%'}"></div></div>
            <span class="rv">{{ z.online }}/{{ z.total }} · {{ z.rate }}%</span>
          </div>
        </el-col>
        <el-col :span="12">
          <div style="font-weight:600;margin-bottom:8px">终端类型分布</div>
          <div class="rate-row" v-for="t in report.types" :key="t.type">
            <span class="rz">{{ t.type }}</span>
            <div class="rbar"><div class="rbar-in rbar-type" :style="{width: (t.total * 100 / (report.types[0]?.total || 1)) + '%'}"></div></div>
            <span class="rv">{{ t.total }} 台</span>
          </div>
          <el-alert type="info" :closable="false" style="margin-top:14px"
                    title="历史在线率曲线：每小时快照自部署起自动积累，次日即可查看趋势" />
        </el-col>
      </el-row>
      <div v-if="report.history.length" style="margin-top:16px">
        <div style="font-weight:600;margin-bottom:8px">近 48 小时在线率走势</div>
        <div style="display:flex;align-items:flex-end;gap:2px;height:120px">
          <div v-for="h in report.history" :key="h.hour" style="flex:1;text-align:center">
            <div :style="{height: Math.max(h.rate, 2) + 'px', background: 'var(--accent)', borderRadius: '2px 2px 0 0'}"></div>
          </div>
        </div>
        <div style="display:flex;gap:2px;margin-top:4px">
          <span v-for="h in report.history" :key="h.hour" style="flex:1;font-size:9px;color:var(--text-dim);overflow:hidden;white-space:nowrap">{{ h.hour.split(' ')[1] }}</span>
        </div>
      </div>
    </el-dialog>

    <!-- 批量补全对话框 -->
    <el-dialog v-model="enrichOpen" title="🧩 批量信息补全工作台" width="760px" top="5vh">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
                title="规则：名称含关键词的终端 → 批量设置区域/责任人。先预览后执行，避免误操作。" />
      <div v-for="(r, idx) in enrichRules" :key="idx" style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
        <el-input v-model="r.kw" placeholder="名称含关键词，如：一期PDA" style="width:200px" size="small" />
        <el-input v-model="r.zone" placeholder="设为区域，如：一期" style="width:160px" size="small" />
        <el-input v-model="r.owner" placeholder="责任人/班组" style="width:160px" size="small" />
        <el-button size="small" @click="enrichRules.splice(idx, 1)">删除</el-button>
      </div>
      <el-button size="small" @click="enrichRules.push({kw:'', zone:'', owner:''})">+ 添加规则</el-button>
      <div style="margin-top:12px">
        <el-button size="small" @click="enrichPreview" :loading="enrichPreviewing">🔍 预览命中</el-button>
        <el-button size="small" type="primary" @click="enrichApply" :loading="enrichApplying">✓ 执行更新</el-button>
      </div>
      <div v-if="enrichPreviewRows.length" style="margin-top:12px">
        <el-table :data="enrichPreviewRows" size="small" border max-height="260">
          <el-table-column label="关键词" width="120"><template #default="{row}">{{ row.kw }}</template></el-table-column>
          <el-table-column label="命中设备" width="90" align="center"><template #default="{row}">{{ row.match }}</template></el-table-column>
          <el-table-column label="设为区域" width="90"><template #default="{row}">{{ row.zone || '—' }}</template></el-table-column>
          <el-table-column label="责任人" width="90"><template #default="{row}">{{ row.owner || '—' }}</template></el-table-column>
          <el-table-column label="样例"><template #default="{row}">{{ (row.sample || []).join('、') }}</template></el-table-column>
        </el-table>
      </div>
    </el-dialog>

<!-- 终端详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="'终端详情'" size="420px">
      <template v-if="detailRow">
        <div style="font-size:15px;font-weight:600;margin-bottom:12px">{{ detailRow.name }}</div>
        <div class="detail-grid">
          <div class="detail-item"><span class="dk">MAC地址</span><span>{{ detailRow.mac.toUpperCase() }}</span></div>
          <div class="detail-item"><span class="dk">终端类型</span><span>{{ (detailRow.note || '').split(' · ')[0] || '其他类型' }}</span></div>
          <div class="detail-item"><span class="dk">IP地址</span><span>{{ detailRow.ip || '—' }}</span></div>
          <div class="detail-item"><span class="dk">所属组</span><span>PSK认证组</span></div>
          <div class="detail-item"><span class="dk">认证类型</span><span>WPA-PSK/WPA2-PSK(个人)</span></div>
          <div class="detail-item"><span class="dk">角色</span><span>默认角色</span></div>
          <div class="detail-item"><span class="dk">接入位置</span><span>{{ detailRow.ap_name || '—' }}</span></div>
          <div class="detail-item"><span class="dk">区域</span><span>{{ detailRow.zone || '未分区' }}</span></div>
          <div class="detail-item"><span class="dk">接入网络</span><span>Production network</span></div>
          <div class="detail-item"><span class="dk">状态</span>
            <span :style="{color: detailRow.online ? 'var(--green)' : 'var(--text-dim)'}">{{ detailRow.online ? '🟢 在线' : '⚪ 离线' }}</span></div>
          <div class="detail-item"><span class="dk">最近接入</span><span>{{ detailRow.last_seen || '—' }}</span></div>
          <div class="detail-item"><span class="dk">责任人</span><span>{{ detailRow.owner || '—' }}</span></div>
          <div class="detail-item" v-if="detailRow.note && detailRow.note.includes('最近接入')"><span class="dk">最近使用</span><span>{{ detailRow.note.split(' · ')[1] || '—' }}</span></div>
        </div>
        <div style="font-size:14px;font-weight:600;margin:16px 0 8px">🏷️ 资产联动</div>
        <div v-if="detailRow.asset_tag" class="detail-grid">
          <div class="detail-item"><span class="dk">资产编号</span><span>{{ detailRow.asset_tag }}</span></div>
          <div class="detail-item"><span class="dk">资产名称</span><span>{{ detailRow.asset_name }}</span></div>
          <div class="detail-item"><span class="dk">使用人</span><span>{{ detailRow.custodian || '—' }}</span></div>
        </div>
        <el-alert v-else type="warning" :closable="false" style="margin-top:6px"
                  title="未关联资产：可使用「自动关联资产」按钮匹配，或在编辑中手动关联" />
        <div style="font-size:14px;font-weight:600;margin:16px 0 8px">🛡️ 区域围栏</div>
        <div class="detail-item">
          <span class="dk">允许区域</span>
          <span>{{ (detailRow.allowed_zones && detailRow.allowed_zones.length) ? detailRow.allowed_zones.join('、') : '不限制' }}</span>
        </div>
        <el-button size="small" style="margin-top:8px" @click="setAllowedZone(detailRow)">设置允许区域</el-button>
        <el-alert type="info" :closable="false" style="margin-top:14px"
                  title="频段/信道/协商速率等实时射频参数请在 NAC 平台查看该终端详情" />
      </template>
    </el-drawer>

<!-- 编辑对话框 -->
    <el-dialog v-model="edit" :title="'编辑设备 · ' + (editing ? (editing.name || editing.mac) : '')" width="460px">
      <template v-if="editing">
        <el-form label-width="90px" size="small">
          <el-form-item label="设备名称"><el-input v-model="editing.name" /></el-form-item>
          <el-form-item label="设备编号"><el-input v-model="editing.device_no" /></el-form-item>
          <el-form-item label="责任人"><el-input v-model="editing.owner" placeholder="责任人/班组" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="editing.note" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <div style="text-align:right">
          <el-button @click="edit = false">取消</el-button>
          <el-button type="primary" @click="saveEdit">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 平面图对话框 -->
    <el-dialog v-model="mapOpen" title="🗺 车间平面图 · 设备位置" width="78%" top="4vh"
               @opened="initMap">
      <div style="display:flex;gap:10px;margin-bottom:10px;align-items:center">
        <el-upload :show-file-list="false" accept="image/*"
                   :http-request="uploadFloor" action="">
          <el-button size="small">🖼 上传平面图底图</el-button>
        </el-upload>
        <span style="font-size:12px;color:var(--text-dim)">
          拖拽设备圆点到实际位置；点击「保存点位」后固定。在线=绿色，离线=灰色，失联=红色。</span>
        <div style="flex:1"></div>
        <el-button size="small" @click="autoPlace">按区域自动排布</el-button>
        <el-button type="primary" size="small" :loading="savingMap" @click="saveMap">保存点位</el-button>
      </div>
      <div style="position:relative;display:inline-block;width:100%"
           @mousedown="mapDragStart" @mousemove="mapDragMove" @mouseup="mapDragEnd" @mouseleave="mapDragEnd">
        <img v-if="mapImg" :src="mapImg" style="width:100%;display:block;user-select:none"
             draggable="false" ref="mapImgEl" />
        <div v-else style="border:2px dashed var(--border);border-radius:8px;padding:60px;text-align:center;color:var(--text-dim)">
          暂无平面图——点击上方「上传平面图底图」
        </div>
        <div v-for="d in mapDevices" :key="d.id"
             :style="{position:'absolute', left:'calc(' + d.px + '% - 9px)', top:'calc(' + d.py + '% - 9px)',
                      width:'18px',height:'18px',borderRadius:'50%',cursor:'grab',
                      background: d.color, border:'2px solid #fff',
                      boxShadow:'0 1px 4px rgba(0,0,0,.4)'}"
             :title="d.name">
        </div>
      </div>
    </el-dialog>

    <!-- AP 清单对话框 -->
    <el-dialog v-model="apOpen" title="📡 信锐 AP 接入点清单" width="92%" top="4vh">
      <el-input v-model="apKw" placeholder="搜索名称 / MAC" size="small" style="margin-bottom:10px" clearable />
      <el-table :data="apList" size="small" max-height="480" border>
        <el-table-column label="AP 名称" min-width="130"><template #default="{row}">{{ row.name }}</template></el-table-column>
        <el-table-column label="在线" width="65" align="center"><template #default="{row}">
          <span :style="{color: row.online ? 'var(--green)' : 'var(--text-dim)'}">{{ row.online ? '●' : '○' }}</span>
        </template></el-table-column>
        <el-table-column label="IP" width="110"><template #default="{row}">{{ row.ip || '—' }}</template></el-table-column>
        <el-table-column label="型号" width="130"><template #default="{row}">{{ row.model || '—' }}</template></el-table-column>
        <el-table-column label="固件版本" width="150"><template #default="{row}">{{ row.firmware || '—' }}</template></el-table-column>
        <el-table-column label="CPU" width="60" align="center"><template #default="{row}">{{ row.cpu || '—' }}</template></el-table-column>
        <el-table-column label="内存" width="60" align="center"><template #default="{row}">{{ row.mem || '—' }}</template></el-table-column>
        <el-table-column label="在线时长" width="170"><template #default="{row}">{{ row.uptime || '—' }}</template></el-table-column>
        <el-table-column label="所属组/区域" min-width="150"><template #default="{row}">{{ row.group || row.zone || '—' }}</template></el-table-column>
        <el-table-column label="SN" width="110"><template #default="{row}">{{ row.sn || '—' }}</template></el-table-column>
      </el-table>
    </el-dialog>

    <!-- AC 对接对话框（信锐） -->
    <el-dialog v-model="acOpen" title="🔗 信锐 AC 对接（自动同步终端位置）" width="680px">
      <el-tabs v-model="acTab">
        <el-tab-pane label="📄 CSV 导入" name="csv">
          <el-alert type="info" :closable="false" style="margin-bottom:12px"
                    title="在信锐 AC 管理平台「终端用户/无线终端」导出 CSV，上传后自动同步到设备台账（自动识别列：MAC/终端名/AP/信号/IP/SSID）。" />
          <el-upload drag :show-file-list="false" accept=".csv" :http-request="uploadSundrayCsv">
            <div style="padding:24px 0">
              <div style="font-size:28px">📄</div>
              <div style="margin-top:6px">点击或拖拽信锐导出的 CSV 文件到此处</div>
              <div style="font-size:12px;color:var(--text-dim);margin-top:4px">自动识别 GBK/UTF-8 编码，按表头智能匹配列</div>
            </div>
          </el-upload>
          <el-alert v-if="csvResult" :type="csvResult.ok ? 'success' : 'error'" :closable="false"
                    :title="csvResult.title" :description="csvResult.detail" style="margin-top:10px" />
        </el-tab-pane>

        <el-tab-pane label="🛰 SNMP 对接" name="snmp">
          <el-alert type="info" :closable="false" style="margin-bottom:12px"
                    title="在信锐后台开启 SNMP v1/v2（团体名+允许本系统服务器 IP），填入 AC 地址即可自动采集 AP 清单（每5分钟）。已实测支持信锐 WAC m5000。" />
          <el-form label-width="130px" size="small">
            <el-form-item label="AC 管理地址">
              <el-input v-model="sundrayCfg.base_url" placeholder="如 192.168.1.100" style="width:220px" />
            </el-form-item>
            <el-form-item label="SNMP 团体名"><el-input v-model="sundrayCfg.community" style="width:220px" /></el-form-item>
          </el-form>
          <el-alert v-if="acTestResult" :type="acTestResult.ok ? 'success' : 'error'" :closable="false"
                    :title="acTestResult.title" :description="acTestResult.detail" style="margin-bottom:10px" />
          <div style="text-align:right">
            <el-button :loading="acTesting" @click="testSnmp">测试连接</el-button>
            <el-button type="primary" :loading="snmpSyncing" @click="syncSnmp">同步 AP 清单</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="📶 NAC 终端表" name="nac">
          <el-alert type="success" :closable="false" style="margin-bottom:12px"
                    title="信锐 NAC「终端 → 在线用户」的无线终端表（MAC/用户名/终端类型/设备名称/IP/接入点/最近接入时间），导出 CSV 后拖入下方即可按接入点自动分区建档。" />
          <el-upload drag :show-file-list="false" accept=".csv" :http-request="uploadNacCsv">
            <div style="padding:20px 0">
              <div style="font-size:26px">📶</div>
              <div style="margin-top:4px">拖入 NAC 导出的无线用户 CSV</div>
            </div>
          </el-upload>
          <el-alert v-if="csvResult" :type="csvResult.ok ? 'success' : 'error'" :closable="false"
                    :title="csvResult.title" :description="csvResult.detail" style="margin-top:10px" />
        </el-tab-pane>

        <el-tab-pane label="📶 NAC 终端对接" name="nac">
          <el-alert type="success" :closable="false" style="margin-bottom:12px"
                    title="填写 NAC 管理地址与账号（只读账号即可），系统自动登录拉取「无线用户」终端表——每5分钟同步一次，终端按接入点 AP 自动分区建档。" />
          <el-form label-width="130px" size="small">
            <el-form-item label="NAC 管理地址">
              <el-input v-model="nacCfg.nac_url" placeholder="如 https://192.168.1.100" style="width:240px" />
            </el-form-item>
            <el-form-item label="账号"><el-input v-model="nacCfg.nac_user" style="width:220px" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="nacCfg.nac_pass" type="password" style="width:220px" /></el-form-item>
          </el-form>
          <el-alert v-if="nacTestResult" :type="nacTestResult.ok ? 'success' : 'error'" :closable="false"
                    :title="nacTestResult.title" :description="nacTestResult.detail" style="margin-bottom:10px" />
          <div style="text-align:right">
            <el-button :loading="nacTesting" @click="testNac">测试连接</el-button>
            <el-button type="primary" :loading="nacSyncing" @click="syncNac">同步终端清单</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="🛰 华为 SSH（旧）" name="ssh">
          <el-alert type="info" :closable="false" style="margin-bottom:12px"
                title="采集脚本部署在 .37 宿主机 crontab（每5分钟），通过 SSH 执行华为 display station all 解析后上报心跳。修改配置后点击「测试连接」验证。" />
          <el-form label-width="120px" size="small" disabled>
            <el-form-item label="AC 管理 IP"><el-input v-model="acCfg.ac_host" style="width:220px" /></el-form-item>
            <el-form-item label="SSH 端口"><el-input v-model="acCfg.ac_port" style="width:100px" /></el-form-item>
            <el-form-item label="用户名"><el-input v-model="acCfg.ac_user" style="width:220px" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="acCfg.ac_pass" type="password" style="width:220px" /></el-form-item>
          </el-form>
          <el-alert v-if="acTestResult" :type="acTestResult.ok ? 'success' : 'error'" :closable="false"
                    :title="acTestResult.title" :description="acTestResult.detail" style="margin-bottom:10px" />
          <div style="text-align:right">
            <el-button disabled>⬇️ 下载采集脚本+安装说明</el-button>
            <el-button type="primary" disabled :loading="acTesting" @click="testAc">测试连接</el-button>
          </div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:8px">当前 AC 为信锐品牌，此页仅作华为场景预留。</div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 漫游轨迹对话框 -->
    <el-dialog v-model="trackOpen" :title="'🛰 漫游轨迹 · ' + (trackDev ? (trackDev.name || trackDev.mac) : '')" width="520px">
      <el-timeline v-if="trackRows.length">
        <el-timeline-item v-for="(t, i) in trackRows" :key="i" :timestamp="t.time" placement="top"
                          :color="i === 0 ? '#e5455e' : '#3477f6'">
          {{ t.ap }} <el-tag size="mini" style="margin-left:6px">{{ t.reason || '关联' }}</el-tag>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无漫游记录（设备可能一直停留在同一 AP）" />
    </el-dialog>

    <!-- 手动添加设备对话框 -->
    <el-dialog v-model="addOpen" title="➕ 添加移动设备" width="480px">
      <el-form label-width="100px" size="small">
        <el-form-item label="MAC 地址" required>
          <el-input v-model="addForm.mac" placeholder="如 AABBCCDDEE01 或 AA:BB:CC:DD:EE:01" maxlength="17" />
        </el-form-item>
        <el-form-item label="设备名称"><el-input v-model="addForm.name" placeholder="如 车间PDA-01" /></el-form-item>
        <el-form-item label="设备编号"><el-input v-model="addForm.device_no" /></el-form-item>
        <el-form-item label="型号"><el-input v-model="addForm.device_model" placeholder="如 Honeywell EDA50" /></el-form-item>
        <el-form-item label="责任人"><el-input v-model="addForm.owner" placeholder="责任人/班组" /></el-form-item>
        <el-form-item label="责任部门"><el-input v-model="addForm.department" placeholder="部门名称" /></el-form-item>
        <el-form-item label="区域"><el-input v-model="addForm.zone" placeholder="如 A区（可留空由AP自动推断）" /></el-form-item>
        <el-form-item label="AP 名称"><el-input v-model="addForm.ap_name" placeholder="如 AP-A区-03" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="addForm.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <div style="text-align:right">
        <el-button @click="addOpen = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="submitAdd">保存</el-button>
      </div>
    </el-dialog>

    <!-- 删除设备对话框 -->
    <el-dialog v-model="delOpen" title="🗑 删除设备" width="520px">
      <el-alert type="warning" :closable="false" style="margin-bottom:10px"
                title="勾选要删除的设备，删除后心跳会自动重新建档（如设备仍在上报）。" />
      <div style="max-height:400px;overflow:auto;border:1px solid var(--border);border-radius:6px;padding:6px">
        <el-checkbox v-model="delAll" style="display:block;padding:4px 8px"
                     @change="delSel = delAll ? items.map(x => x.id) : []">全选</el-checkbox>
        <el-checkbox v-for="x in items" :key="x.id" v-model="delMap[x.id]"
                     style="display:flex;padding:4px 8px"
                     @change="syncSel(x.id, $event)">
          {{ x.name || x.mac }} <span style="color:var(--text-dim);margin-left:8px">{{ x.mac }}</span>
          <el-tag v-if="x.zone" size="mini" style="margin-left:8px">{{ x.zone }}</el-tag>
        </el-checkbox>
      </div>
      <div style="text-align:right;margin-top:10px">
        <span style="float:left;color:var(--text-dim);font-size:13px;line-height:32px">已选 {{ delSel.length }} 台</span>
        <el-button @click="delOpen = false">取消</el-button>
        <el-button type="danger" :disabled="!delSel.length" :loading="deleting" @click="doDelete">删除选中</el-button>
      </div>
    </el-dialog>

    <!-- 二维码标签对话框 -->
    <el-dialog v-model="labelOpen" title="🏷 二维码标签（打印后贴到设备背面）" width="720px">
      <div style="margin-bottom:10px">
        <el-button size="small" @click="labelAll = !labelAll">{{ labelAll ? '取消全选' : '全选' }}</el-button>
        <span style="color:var(--text-dim);font-size:13px;margin-left:8px">勾选要打印的设备，扫码打开「扫码登记」页自动识别设备</span>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:12px;max-height:440px;overflow:auto">
        <div v-for="x in items" :key="x.id"
             style="width:150px;border:1px solid var(--border);border-radius:8px;padding:10px;text-align:center">
          <el-checkbox v-model="labelSel[x.id]" style="float:left" />
          <div :id="'qrholder-' + x.id" style="display:flex;justify-content:center;min-height:100px"></div>
          <div style="font-size:13px;font-weight:600;margin-top:6px">{{ x.name || x.mac }}</div>
          <div style="font-size:11px;color:var(--text-dim)">{{ x.device_no || x.mac }}</div>
          <div style="font-size:11px;color:var(--text-dim)">{{ x.owner || '未指定责任人' }}</div>
        </div>
      </div>
      <div style="text-align:right;margin-top:10px">
        <el-button type="primary" @click="printLabels">🖨 打印标签</el-button>
      </div>
    </el-dialog>

    <!-- 扫码登记对话框 -->
    <el-dialog v-model="scanOpen" title="📷 扫码领用 / 归还登记" width="480px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
                title="用 PDA 扫描设备背面的二维码，打开登记页输入姓名即可完成领用/归还。此处也可手动登记：" />
      <el-form label-width="90px" size="small">
        <el-form-item label="设备">
          <el-select v-model="scanForm.mac" filterable placeholder="选择设备" style="width:100%">
            <el-option v-for="x in items" :key="x.id" :label="x.name || x.mac" :value="x.mac" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作">
          <el-radio-group v-model="scanForm.action">
            <el-radio value="take">📤 领用</el-radio>
            <el-radio value="return">📥 归还</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="经手人" required><el-input v-model="scanForm.person" placeholder="姓名/班组" /></el-form-item>
      </el-form>
      <div style="text-align:right">
        <el-button @click="scanOpen = false">取消</el-button>
        <el-button type="primary" @click="submitScan">登记</el-button>
      </div>
      <h4 style="margin:14px 0 8px">最近登记</h4>
      <div style="max-height:220px;overflow:auto;font-size:13px;line-height:2">
        <div v-for="l in scanLogs" :key="l.id">
          <el-tag size="mini" :type="l.action === 'take' ? 'warning' : 'success'">{{ l.action_text }}</el-tag>
          {{ l.device }} ← {{ l.person }} <span style="color:var(--text-dim)">{{ l.time }}</span>
        </div>
        <div v-if="!scanLogs.length" style="color:var(--text-dim)">暂无记录</div>
      </div>
    </el-dialog>

    <!-- 趋势图对话框 -->
    <el-dialog v-model="trendOpen" :title="'📈 心跳趋势 · ' + (trendDev || '')" width="680px">
      <div ref="trendChart" style="height:300px"></div>
      <div style="font-size:12px;color:var(--text-dim);margin-top:6px">
        电量持续下降且不上充 = 设备被遗忘在角落；长期无心跳 = 设备关机/离网，需要找回。
      </div>
    </el-dialog>

    <!-- 入网指引对话框 -->
    <el-dialog v-model="guideOpen" title="📖 PDA / 平板入网配置指引" width="640px">
      <template v-if="guide">
        <el-alert type="warning" :closable="false" style="margin-bottom:14px" :title="guide.intro" />
        <div v-for="s in guide.steps" :key="s.no" style="margin-bottom:16px">
          <div style="font-weight:600">{{ s.no }}. {{ s.title }}</div>
          <div style="font-size:13px;color:var(--text-dim);margin:4px 0">为什么要做：{{ s.why }}</div>
          <ol style="margin:0;padding-left:20px;font-size:13px;line-height:2">
            <li v-for="(h, hi) in s.how" :key="hi">{{ h }}</li>
          </ol>
        </div>
        <el-alert type="success" :closable="false" :title="guide.checklist" />
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog v-model="importOpen" title="📥 批量导入设备台账" width="560px">
      <el-tabs v-model="importTab">
        <el-tab-pane label="📄 Excel 文件导入" name="file">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <span style="font-size:13px;color:var(--text-dim)">下载模板填写后上传，支持 .xlsx</span>
            <el-button size="small" @click="downloadImportTpl">📥 下载模板</el-button>
          </div>
          <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx,.xls"
                     :on-change="onImportFile" :on-remove="() => importFile = null"
                     :on-exceed="() => ElMessage.warning('一次只能上传一个文件')">
            <div style="padding:24px">
              <div style="font-size:34px">📊</div>
              <p style="margin:6px 0">将 .xlsx 文件拖到此处，或点击选择</p>
              <p style="font-size:12px;color:var(--text-dim);margin:0">
                列顺序：MAC地址 → 设备名称 → 设备编号 → 设备型号 → 责任人 → 部门 → 区域 → AP名称 → 备注
              </p>
            </div>
          </el-upload>
        </el-tab-pane>
        <el-tab-pane label="📋 粘贴表格" name="paste">
          <el-alert type="info" :closable="false" style="margin-bottom:10px"
                    title="粘贴 Excel 表格（列顺序：MAC地址 → 设备名称 → 设备编号 → 责任人 → 区域 → AP名称），首行表头自动忽略" />
          <el-input v-model="importText" type="textarea" :rows="8"
                    placeholder="AABBCCDDEE01	车间PDA-01	PDA-001	装配一组	A区	AP-A区-01" />
        </el-tab-pane>
      </el-tabs>
      <div style="text-align:right;margin-top:10px">
        <el-button @click="importOpen = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="importTab === 'file' && !importFile"
                   @click="doImport">{{ importTab === 'file' ? '导入 Excel' : '导入' }}</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '../api'

const loading = ref(false)
const items = ref([])
const sum = ref({})
const q = ref({ kw: '', state: '', zone: '' })
const edit = ref(false), editing = ref(null)
const importOpen = ref(false), importText = ref('')
const importTab = ref('file'), importFile = ref(null), importing = ref(false)
const addOpen = ref(false), adding = ref(false)
const delOpen = ref(false), deleting = ref(false), delAll = ref(false)
const labelOpen = ref(false), labelAll = ref(false), labelSel = ref({})
const scanOpen = ref(false), scanLogs = ref([])
const scanForm = ref({ mac: '', action: 'take', person: '' })
watch(scanOpen, v => { if (v) openScanLogs() })

// ── 平面图 ──
const mapOpen = ref(false), mapImg = ref(''), savingMap = ref(false)
const mapDevices = ref([])
let dragTarget = null

async function openMap() {
  mapOpen.value = true
  const d = await api.get('/pda/map/')
  mapImg.value = d.image || ''
  const colors = { online: '#12a578', offline: '#9aa8c7', stale: '#e5455e' }
  mapDevices.value = (d.devices || []).map(x => ({
    id: x.id, name: x.name || x.mac, zone: x.zone,
    px: x.pos_x != null ? x.pos_x : 50, py: x.pos_y != null ? x.pos_y : 50,
    color: x.stale ? colors.stale : (x.online ? colors.online : colors.offline),
  }))
}

async function uploadFloor(opt) {
  const fd = new FormData()
  fd.append('image', opt.file)
  await api.post('/pda/map/upload/', fd)
  const d = await api.get('/pda/map/')
  mapImg.value = d.image
  ElMessage.success('平面图已上传')
}

function mapDragStart(e) {
  const t = e.target
  if (t.style && t.style.borderRadius === '50%') {
    dragTarget = mapDevices.value.find(d => d.name === t.title)
  }
}
function mapDragMove(e) {
  if (!dragTarget) return
  e.preventDefault()
  const holder = e.currentTarget.getBoundingClientRect()
  dragTarget.px = Math.min(99, Math.max(1, +(((e.clientX - holder.left) / holder.width) * 100).toFixed(1)))
  dragTarget.py = Math.min(99, Math.max(1, +(((e.clientY - holder.top) / holder.height) * 100).toFixed(1)))
}
function mapDragEnd() { dragTarget = null }

function autoPlace() {
  // 按 zone 分列自动排布
  const groups = {}
  mapDevices.value.forEach(d => { (groups[d.zone || '未分区'] = groups[d.zone || '未分区'] || []).push(d) })
  const keys = Object.keys(groups)
  keys.forEach((z, zi) => {
    groups[z].forEach((d, di) => {
      d.px = +(8 + (zi + 0.5) * (84 / keys.length)).toFixed(1)
      d.py = +(10 + (di % 10) * 8).toFixed(1)
    })
  })
  ElMessage.success('已按区域自动排布，调整后点「保存点位」')
}

async function saveMap() {
  savingMap.value = true
  try {
    await api.post('/pda/map/save/', {
      devices: mapDevices.value.map(d => ({ id: d.id, pos_x: d.px, pos_y: d.py })),
    })
    ElMessage.success('点位已保存')
  } finally { savingMap.value = false }
}
const trendOpen = ref(false), trendDev = ref(''), trendChart = ref(null)
const guideOpen = ref(false), guide = ref(null)
let _qrRendered = false
const delSel = ref([])
const delMap = ref({})

function openDelete() {
  delMap.value = {}
  delSel.value = []
  delAll.value = false
  delOpen.value = true
}
function syncSel(id, checked) {
  if (checked) { if (!delSel.value.includes(id)) delSel.value.push(id) }
  else delSel.value = delSel.value.filter(x => x !== id)
}
async function doDelete() {
  deleting.value = true
  try {
    const r = await api.post('/pda/delete/', { ids: delSel.value })
    ElMessage.success('已删除 ' + r.deleted + ' 台设备')
    delOpen.value = false
    load()
  } finally { deleting.value = false }
}
const addForm = ref({ mac: '', name: '', device_no: '', device_model: '',
                      owner: '', department: '', zone: '', ap_name: '', note: '' })

async function submitAdd() {
  if (!addForm.value.mac.trim()) { ElMessage.warning('MAC 地址必填'); return }
  adding.value = true
  try {
    const r = await api.post('/pda/import/', { rows: [addForm.value] })
    if (r.errors && r.errors.length) { ElMessage.error(r.errors[0]); return }
    ElMessage.success(`设备已${r.created ? '添加' : '更新'}`)
    addOpen.value = false
    addForm.value = { mac: '', name: '', device_no: '', device_model: '',
                      owner: '', department: '', zone: '', ap_name: '', note: '' }
    load()
  } finally { adding.value = false }
}
const acOpen = ref(false), acTesting = ref(false), acTestResult = ref(null)
const acTab = ref('csv')
const csvResult = ref(null)
const sundrayCfg = ref({ base_url: '192.168.1.100', community: 'public' })
const snmpSyncing = ref(false)
const snmpCfg = ref({ ac_ip: '', community: 'public', last_sync: null, ap_count: 0, aps: [] })
const nacCfg = ref({ nac_url: 'https://192.168.1.100', nac_user: '', nac_pass: '' })
const nacTesting = ref(false), nacSyncing = ref(false), nacTestResult = ref(null)

async function loadNacConfig() {
  try {
    const r = await api.get('/pda/nac/config/')
    if (r.nac_url) {
      nacCfg.value.nac_url = r.nac_url
      nacCfg.value.nac_user = r.nac_user
    }
  } catch (e) { /* ignore */ }
}

async function testNac() {
  nacTesting.value = true
  nacTestResult.value = null
  try {
    const r = await api.post('/pda/nac/test/', nacCfg.value, { timeout: 60000 })
    nacTestResult.value = r.ok
      ? { ok: true, title: '✓ 连接成功', detail: r.detail }
      : { ok: false, title: '✗ 连接失败', detail: r.error }
  } catch (e) { nacTestResult.value = { ok: false, title: '✗ 请求失败', detail: String(e).slice(0, 120) } }
  finally { nacTesting.value = false }
}

async function syncNac() {
  nacSyncing.value = true
  nacTestResult.value = null
  try {
    const r = await api.post('/pda/nac/sync/', nacCfg.value, { timeout: 180000 })
    if (r.ok) {
      nacTestResult.value = { ok: true, title: '✓ 同步完成',
        detail: `新增 ${r.created}，更新 ${r.updated}（共 ${r.total} 条终端）` }
      load()
    } else {
      nacTestResult.value = { ok: false, title: '✗ 同步失败', detail: r.error }
    }
  } catch (e) { nacTestResult.value = { ok: false, title: '✗ 请求失败', detail: String(e).slice(0, 120) } }
  finally { nacSyncing.value = false }
}
const apOpen = ref(false), apKw = ref('')
const page = ref(1), pageSize = ref(10)
const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return items.value.slice(start, start + pageSize.value)
})
watch([items, pageSize], () => { page.value = 1 })
const apList = computed(() => {
  const kw = apKw.value.trim().toLowerCase()
  const rows = (snmpCfg.value.aps || []).map(a => ({
    ...a,
    zone: (a.name && (a.name.match(/^[\u4e00-\u9fa5]{2,10}/) || [])[0]) || '未分组'
  }))
  if (!kw) return rows
  return rows.filter(a => (a.name || '').toLowerCase().includes(kw) ||
                          (a.mac || '').includes(kw))
})

async function uploadNacCsv(opt) {
  csvResult.value = null
  const fd = new FormData()
  fd.append('file', opt.file)
  try {
    const r = await api.post('/pda/sundray/csv/', fd)
    csvResult.value = { ok: true,
      title: `✓ 同步完成：新增 ${r.created}，更新 ${r.updated}`,
      detail: `共 ${r.total_rows} 行，跳过无效 ${r.skipped} 条。区域按接入点 AP 名自动推断。` }
    load()
    loadSnmpConfig()
  } catch (e) {
    const d = e.response && e.response.data
    csvResult.value = { ok: false, title: '导入失败',
      detail: (d && (d.error || JSON.stringify(d.header))) || String(e).slice(0, 100) }
  }
}

async function testSnmp() {
  acTesting.value = true
  acTestResult.value = null
  try {
    const r = await api.post('/pda/snmp/test/', {
      ac_ip: sundrayCfg.value.base_url,
      community: sundrayCfg.value.community,
    }, { timeout: 30000 })
    acTestResult.value = r.ok
      ? { ok: true, title: '✓ 连接成功', detail: r.detail }
      : { ok: false, title: '✗ 连接失败', detail: r.error }
  } catch (e) { acTestResult.value = { ok: false, title: '✗ 请求失败', detail: String(e).slice(0, 120) } }
  finally { acTesting.value = false }
}

async function syncSnmp() {
  snmpSyncing.value = true
  acTestResult.value = null
  try {
    const r = await api.post('/pda/snmp/sync/', {
      ac_ip: sundrayCfg.value.base_url,
      community: sundrayCfg.value.community,
    }, { timeout: 120000 })
    if (r.ok) {
      acTestResult.value = { ok: true, title: '✓ 同步完成', detail: `已采集 ${r.ap_count} 台 AP（${r.last_sync}）` }
      load()
      loadSnmpConfig()
    } else {
      acTestResult.value = { ok: false, title: '✗ 同步失败', detail: r.error }
    }
  } catch (e) { acTestResult.value = { ok: false, title: '✗ 请求失败', detail: String(e).slice(0, 120) } }
  finally { snmpSyncing.value = false }
}

async function loadSnmpConfig() {
  try {
    const r = await api.get('/pda/snmp/config/')
    if (r.ac_ip) {
      sundrayCfg.value.base_url = r.ac_ip
      sundrayCfg.value.community = r.community || 'public'
    }
  } catch (e) { /* ignore */ }
  try {
    const r2 = await api.get('/pda/snmp/aps/')
    snmpCfg.value = { ac_ip: r2.ac_ip, community: r2.community,
                      last_sync: r2.last_sync, ap_count: r2.ap_count, aps: r2.aps || [],
                      ap_online: (r2.aps || []).filter(a => a.online).length }
  } catch (e) { /* ignore */ }
}

async function uploadSundrayCsv(opt) {
  csvResult.value = null
  const fd = new FormData()
  fd.append('file', opt.file)
  try {
    const r = await api.post('/pda/sundray/csv/', fd)
    csvResult.value = { ok: true,
      title: `✓ 同步完成：新增 ${r.created}，更新 ${r.updated}`,
      detail: `共 ${r.total_rows} 行，跳过无效 ${r.skipped} 条。区域按 AP 名自动推断。` }
    load()
  } catch (e) {
    const d = e.response && e.response.data
    csvResult.value = { ok: false, title: '导入失败',
      detail: (d && (d.error || JSON.stringify(d.header))) || String(e).slice(0, 100) }
  }
}

async function testSundray() {
  acTesting.value = true
  acTestResult.value = null
  try {
    const r = await api.post('/pda/ac/test/', {
      ac_host: sundrayCfg.value.base_url.replace(/^https?:\/\//, ''),
      ac_user: sundrayCfg.value.username,
      ac_pass: sundrayCfg.value.password,
    }, { timeout: 30000 })
    acTestResult.value = r.ok
      ? { ok: true, title: '✓ 连接成功', detail: r.detail }
      : { ok: false, title: '✗ 连接失败', detail: r.error }
  } catch (e) { acTestResult.value = { ok: false, title: '✗ 请求失败', detail: String(e).slice(0, 120) } }
  finally { acTesting.value = false }
}
const acCfg = ref({ ac_host: '', ac_port: '22', ac_user: 'admin', ac_pass: '' })
const trackOpen = ref(false), trackDev = ref(null), trackRows = ref([])

async function testAc() {
  acTesting.value = true
  try {
    const r = await api.post('/pda/ac/test/', acCfg.value, { timeout: 30000 })
    acTestResult.value = r.ok
      ? { ok: true, title: '✓ 连接成功', detail: r.detail }
      : { ok: false, title: '✗ 连接失败', detail: r.error }
  } catch (e) { acTestResult.value = { ok: false, title: '✗ 请求失败', detail: String(e).slice(0, 120) } }
  finally { acTesting.value = false }
}

function downloadScript() {
  const conf = JSON.stringify({
    AC_HOST: acCfg.value.ac_host, AC_PORT: acCfg.value.ac_port || '22',
    AC_USER: acCfg.value.ac_user, AC_PASS: acCfg.value.ac_pass,
  }, null, 2)
  ElMessage.info('脚本已开始下载，按说明放入 .37 宿主机 /data/scripts/ 并配置 crontab')
  const resp = api.get('/pda/ac/script/', { responseType: 'blob' }).then(resp => {
    // 后端返回的脚本已含配置
    const url = URL.createObjectURL(resp)
    const a = document.createElement('a')
    a.href = url; a.download = 'huawei_ac_collect.py'; a.click()
    URL.revokeObjectURL(url)
  })
}

async function showTrack(row) {
  trackDev.value = row
  const r = await api.get(`/pda/devices/${row.id}/track/`)
  trackRows.value = r.tracks || []
  trackOpen.value = true
}
let timer = null

async function load() {
  loading.value = true
  try {
    const params = {}
    if (q.value.kw) params.kw = q.value.kw
    if (q.value.state) params.state = q.value.state
    if (q.value.zone) params.zone = q.value.zone
    const d = await api.get('/pda/devices/', { params })
    items.value = d.items
    sum.value = d.summary
  } finally { loading.value = false }
}

function rowClass({ row }) { return row.stale ? 'stale-row' : '' }
function rowTag(row) {
  if (row.online) return 'success'
  if (row.stale) return 'danger'
  return 'info'
}
function rowState(row) {
  if (row.online) return '在线'
  if (row.stale) return '失联'
  return '离线'
}

async function ring(row) {
  const r = await api.post(`/pda/devices/${row.id}/ring/`)
  if (r.ok) ElMessage.success(`响铃指令已下发到 ${row.name || row.mac}（MQTT + 下次心跳双通道）`)
  else ElMessage.warning('MQTT 未就绪，指令已保存，设备心跳时将带回响铃标志')
}

const detailVisible = ref(false)
const detailRow = ref(null)
function detailOpen(row) {
  detailRow.value = row
  detailVisible.value = true
}
const reportOpen = ref(false)
const report = ref({ zones: [], types: [], history: [] })
async function loadReport() {
  try {
    report.value = await api.get('/pda/online_report/')
  } catch (e) { ElMessage.error('报表加载失败') }
}
const enrichOpen = ref(false)
const enrichRules = ref([{ kw: '', zone: '', owner: '' }])
const enrichPreviewRows = ref([])
const enrichPreviewing = ref(false)
const enrichApplying = ref(false)
async function enrichPreview() {
  enrichPreviewing.value = true
  try {
    const r = await api.post('/pda/bulk_enrich/preview/', { rules: enrichRules.value.filter(r => r.kw.trim()) })
    enrichPreviewRows.value = r.preview || []
  } finally { enrichPreviewing.value = false }
}
async function enrichApply() {
  const rules = enrichRules.value.filter(r => r.kw.trim())
  if (!rules.length) { ElMessage.warning('请先填写规则'); return }
  enrichApplying.value = true
  try {
    const r = await api.post('/pda/bulk_enrich/apply/', { rules })
    ElMessage.success(`已更新 ${r.total_updated} 台终端`)
    enrichPreviewRows.value = []
    load()
  } finally { enrichApplying.value = false }
}
const zoneAlarmUnread = ref(0)
const alarmOpen = ref(false)
const alarmRows = ref([])

async function loadZoneAlarms() {
  try {
    const r = await api.get('/pda/zone_alarms/?unread=1')
    zoneAlarmUnread.value = r.unread || 0
    if (alarmOpen.value) alarmRows.value = r.rows || []
  } catch (e) { /* ignore */ }
}

async function openZoneAlarms() {
  alarmOpen.value = true
  try {
    const r = await api.get('/pda/zone_alarms/')
    alarmRows.value = r.rows || []
  } catch (e) {}
}

async function markAlarmsRead() {
  await api.post('/pda/zone_alarms/read/', { all: true })
  zoneAlarmUnread.value = 0
  alarmRows.value = []
  ElMessage.success('已全部标记为已读')
}

async function linkAssets() {
  const loading = ElLoading.service({ fullscreen: true, text: '自动关联资产中...' })
  try {
    const r = await api.post('/pda/link_assets/')
    ElMessage.success(`自动关联 ${r.linked} 台，未匹配 ${r.unmatched_count} 台`)
  } finally { loading.close() }
}

async function setAllowedZone(row) {
  const { value } = await ElMessageBox.prompt(
    '设置该设备允许出现的区域（多个用逗号分隔，留空=不限制）', '区域围栏设置',
    { inputValue: (row.allowed_zones || []).join(','), confirmButtonText: '保存', cancelButtonText: '取消' })
  const zones = value.split(/[,，]/).map(s => s.trim()).filter(Boolean)
  await api.post(`/pda/devices/${row.id}/update/`, { allowed_zones: zones })
  row.allowed_zones = zones
  ElMessage.success('围栏已设置：' + (zones.join('、') || '不限制'))
}

function editOpen(row) { editing.value = { ...row, department: null }; edit.value = true }
async function saveEdit() {
  await api.post(`/pda/devices/${editing.value.id}/update/`, {
    name: editing.value.name, device_no: editing.value.device_no,
    owner: editing.value.owner, note: editing.value.note,
  })
  edit.value = false
  ElMessage.success('已保存')
  load()
}

async function downloadImportTpl() {
  // JWT 在请求头，window.open 不带 token → 用 blob 下载
  const resp = await api.get('/pda/import_template/', { responseType: 'blob' })
  const url = URL.createObjectURL(resp)
  const a = document.createElement('a')
  a.href = url
  a.download = 'pda_import_template.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

function onImportFile(f) { importFile.value = f.raw }

async function doImport() {
  if (importTab.value === 'file') {
    // ── Excel 文件导入 ──
    if (!importFile.value) return
    importing.value = true
    try {
      const fd = new FormData()
      fd.append('file', importFile.value)
      const r = await api.post('/pda/import/', fd)
      ElMessage.success(`导入完成：新增 ${r.created}，更新 ${r.updated}` +
        (r.errors.length ? `，错误 ${r.errors.length} 条` : ''))
      if (r.errors.length) console.warn(r.errors)
      importOpen.value = false
      importFile.value = null
      load()
    } finally { importing.value = false }
    return
  }
  // ── 粘贴文本导入（原逻辑） ──
  const lines = importText.value.split('\n').map(l => l.trim()).filter(Boolean)
  const rows = []
  for (const line of lines) {
    if (/^mac/i.test(line)) continue  // 表头
    const cells = line.split('\t').map(c => c.trim())
    if (!cells[0]) continue
    rows.push({ mac: cells[0], name: cells[1] || '', device_no: cells[2] || '',
                owner: cells[3] || '', zone: cells[4] || '', ap_name: cells[5] || '' })
  }
  const r = await api.post('/pda/import/', { rows })
  ElMessage.success(`导入完成：新增 ${r.created}，更新 ${r.updated}` + (r.errors.length ? `，错误 ${r.errors.length} 条` : ''))
  if (r.errors.length) console.warn(r.errors)
  importOpen.value = false
  importText.value = ''
  load()
}

async function openLabels() {
  labelOpen.value = true
  labelAll.value = false
  labelSel.value = {}
  await load()
  nextTick(() => {
    if (!document.getElementById('qrcodejs')) {
      const s = document.createElement('script')
      s.id = 'qrcodejs'
      s.src = '/vendor/qrcode.min.js'
      document.head.appendChild(s)
    }
    const wait = setInterval(() => {
      if (window.QRCode) { clearInterval(wait); renderQrs() }
    }, 150)
    setTimeout(() => clearInterval(wait), 5000)
  })
}

function renderQrs() {
  items.value.forEach(x => {
    const holder = document.getElementById('qrholder-' + x.id)
    if (holder && !holder.hasChildNodes() && window.QRCode) {
      try { new window.QRCode(holder, { text: x.qr_url || x.qr || (location.origin + '/#/pda-scan?mac=' + x.mac), width: 96, height: 96 }) } catch (e) {}
    }
  })
}

function printLabels() {
  const sel = items.value.filter(x => labelSel.value[x.id])
  if (!sel.length) { ElMessage.warning('请先勾选要打印的设备'); return }
  const win = window.open('', '_blank')
  let cards = ''
  sel.forEach(x => {
    const holder = document.getElementById('qrholder-' + x.id)
    const img = holder ? holder.querySelector('img, canvas') : null
    const qrHtml = img ? (img.tagName === 'CANVAS'
      ? '<img src="' + img.toDataURL() + '" width="120">'
      : '<img src="' + img.src + '" width="120">') : ''
    cards += '<div class="card">' + qrHtml +
      '<div class="n">' + (x.name || x.mac) + '</div>' +
      '<div class="s">' + (x.device_no || x.mac) + '</div>' +
      '<div class="s">责任人: ' + (x.owner || '未指定') + '</div></div>'
  })
  win.document.write('<html><head><title>设备二维码标签</title><style>' +
    'body{font-family:sans-serif} .card{display:inline-block;border:1px dashed #999;' +
    'border-radius:8px;padding:12px;margin:8px;text-align:center;page-break-inside:avoid}' +
    '.n{font-weight:600;font-size:14px;margin-top:6px}.s{font-size:11px;color:#666}' +
    '@media print{.card{page-break-inside:avoid}}</style></head><body>' + cards +
    '</body></html>')
  win.document.close()
  setTimeout(() => win.print(), 400)
}

async function openScanLogs() {
  const r = await api.get('/pda/scan/logs/')
  scanLogs.value = r.logs || []
}

async function submitScan() {
  if (!scanForm.value.mac) { ElMessage.warning('请选择设备'); return }
  if (!scanForm.value.person.trim()) { ElMessage.warning('请填写经手人'); return }
  const r = await api.post('/pda/scan/log/', scanForm.value)
  ElMessage.success(`${r.device} ${r.action_text}登记成功（${r.person}，${r.time}）`)
  openScanLogs()
}

async function showTrend(row) {
  trendDev.value = row.name || row.mac
  trendOpen.value = true
  const r = await api.get(`/pda/devices/${row.id}/history/`)
  nextTick(() => {
    if (!trendChart.value) return
    const ch = echarts.init(trendChart.value)
    const pts = r.points || []
    ch.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 44, right: 44, top: 20, bottom: 46 },
      xAxis: { type: 'category', data: pts.map(p => p.ts), axisLabel: { fontSize: 10 } },
      yAxis: [
        { type: 'value', name: '电量%', min: 0, max: 100 },
        { type: 'value', name: '信号dBm', max: 0 },
      ],
      series: [
        { name: '电量%', type: 'line', smooth: true, data: pts.map(p => p.battery),
          itemStyle: { color: '#12a578' }, connectNulls: false },
        { name: '信号dBm', type: 'line', yAxisIndex: 1, smooth: true, data: pts.map(p => p.rssi),
          itemStyle: { color: '#3477f6' }, connectNulls: false },
      ],
    })
  })
}

async function openGuide() {
  guideOpen.value = true
  if (!guide.value) {
    const r = await api.get('/pda/guide/')
    guide.value = r.guide
  }
}

function exportCsv() {
  const headers = ['类型', '设备名称', '编号', 'MAC', '区域', 'AP名称', '信号', '电量', '状态', '最后心跳', '责任人']
  const rows = items.value.map((x, i) => [
    x.type === 'ap' ? '📡 AP' : '📱 PDA',
    x.name || '', x.device_no || '', x.mac, x.zone || '', x.ap_name || '',
    x.rssi != null ? x.rssi + 'dBm' : '',
    x.battery != null ? x.battery + '%' : '',
    rowState(x), x.last_seen || '', x.owner || '',
  ])
  const csv = [headers, ...rows].map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = '移动设备定位-' + new Date().toISOString().slice(0, 10) + '.csv'; a.click()
  URL.revokeObjectURL(url)
}

// 60s 自动刷新
onMounted(() => { load(); loadSnmpConfig(); loadNacConfig(); loadZoneAlarms(); timer = setInterval(() => { load(); loadZoneAlarms() }, 60000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
:deep(.stale-row) { background: var(--red-bg, #fdeaea) !important; }

.detail-grid { display: flex; flex-direction: column; gap: 10px; }
.detail-item { display: flex; justify-content: space-between; gap: 10px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }
.detail-item .dk { color: var(--text-dim); flex-shrink: 0; }

.rate-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.rate-row .rz { width: 90px; font-size: 13px; text-align: right; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.rate-row .rbar { flex: 1; height: 12px; background: var(--border); border-radius: 6px; overflow: hidden; }
.rate-row .rbar-in { height: 100%; background: var(--accent); border-radius: 6px; }
.rate-row .rbar-in.rbar-type { background: var(--green); }
.rate-row .rv { width: 130px; font-size: 12px; color: var(--text-dim); white-space: nowrap; }
</style>
