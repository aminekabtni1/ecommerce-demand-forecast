import { useEffect, useState, useMemo } from 'react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart, Scatter
} from 'recharts'
import { fetchHealth, fetchKpis, fetchTrends, fetchForecast, fetchAnomalies, fetchProducts, fetchCategories } from './api.js'
import './App.css'

function TooltipCard({ active, payload, label }){
  if(!active || !payload?.length) return null
  return (
    <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:8, padding:'10px 12px', boxShadow:'0 4px 16px rgba(0,0,0,.08)', fontSize:12 }}>
      <div style={{ color:'#64748b', fontWeight:600, marginBottom:6 }}>{label}</div>
      {payload.filter(p=> p.value!=null).map((p,i)=>(
        <div key={i} style={{ display:'flex', justifyContent:'space-between', gap:16, marginTop:3 }}>
          <span style={{ color:'#475569', display:'flex', alignItems:'center', gap:6 }}><span style={{ width:8, height:8, borderRadius:99, background:p.stroke||p.fill||'#0ea5e9', display:'inline-block' }}/>{p.name}</span>
          <span style={{ fontWeight:700, color:'#0f172a' }}>{typeof p.value==='number' ? (p.name.toLowerCase().includes('revenue') ? `$${p.value.toLocaleString()}` : p.value.toLocaleString()) : p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function App(){
  const [health, setHealth] = useState(null)
  const [kpis, setKpis] = useState(null)
  const [trends, setTrends] = useState([])
  const [forecast, setForecast] = useState({forecast:[], history:[]})
  const [anomalies, setAnomalies] = useState([])
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [filters, setFilters] = useState({ days:90, category:'', product_id:'', horizon:30, z:2.5 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(()=>{
    Promise.all([fetchHealth(), fetchProducts(), fetchCategories()])
      .then(([h,p,c])=>{ setHealth(h); setProducts(p); setCategories(c)})
      .catch(e=> setError(e.message))
  },[])
  useEffect(()=>{
    setLoading(true); setError('')
    Promise.all([
      fetchKpis(30).then(setKpis).catch(()=>{}),
      fetchTrends({ days: filters.days, ...(filters.category?{category:filters.category}:{}), ...(filters.product_id?{product_id:filters.product_id}:{}) }).then(setTrends).catch(()=>setTrends([])),
      fetchForecast({ ...(filters.product_id?{product_id:filters.product_id}: filters.category?{category:filters.category}:{}), horizon: filters.horizon }).then(setForecast).catch(()=>setForecast({forecast:[],history:[]})),
      fetchAnomalies({ days: filters.days, z_threshold: filters.z, ...(filters.category?{category:filters.category}:{}), ...(filters.product_id?{product_id:filters.product_id}:{}) }).then(setAnomalies).catch(()=>setAnomalies([])),
    ]).finally(()=> setLoading(false))
  },[filters])

  const combined = useMemo(()=>{
    const hist = (forecast.history||[]).map(d=>({ date: d.date?.slice(0,10), actual:d.quantity }))
    const fc = (forecast.forecast||[]).map(d=>({ date: d.date?.slice(0,10), forecast: Math.round(d.forecast), lower: Math.round(d.lower), upper: Math.round(d.upper) }))
    if(fc.length && fc[0].category && !filters.product_id && !filters.category){
      const m={}
      forecast.forecast.forEach(r=>{
        const dt=r.date.slice(0,10)
        if(!m[dt]) m[dt]={date:dt, forecast:0, lower:0, upper:0}
        m[dt].forecast+=Math.round(r.forecast); m[dt].lower+=Math.round(r.lower); m[dt].upper+=Math.round(r.upper)
      })
      return [...hist, ...Object.values(m).sort((a,b)=>a.date.localeCompare(b.date))]
    }
    return [...hist, ...fc]
  },[forecast, filters])

  const anomalyMarkers = useMemo(()=>{
    const map=new Map(combined.map(c=>[c.date,c]))
    return anomalies.map(a=>({ date:a.date.slice(0,10), actual:a.quantity })).filter(a=> map.has(a.date))
  },[anomalies, combined])

  return (
    <div style={{ minHeight:'100vh', background:'#f1f5f9' }}>
      {/* Top bar */}
      <div style={{ background:'#fff', borderBottom:'1px solid #e2e8f0', position:'sticky', top:0, zIndex:10 }}>
        <div style={{ maxWidth:1240, margin:'0 auto', padding:'14px 20px', display:'flex', alignItems:'center', justifyContent:'space-between', gap:16 }}>
          <div>
            <div style={{ fontSize:15, fontWeight:700, color:'#0f172a', letterSpacing:'-.02em' }}>E-Commerce Demand Forecast</div>
            <div style={{ fontSize:12, color:'#64748b', marginTop:2 }}>Daily sales • 30-day forecast • Anomaly detection</div>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:12, fontSize:12 }}>
            <span style={{ display:'flex', alignItems:'center', gap:6, color:'#64748b' }}><span style={{ width:7, height:7, borderRadius:99, background: health?.status==='ok'?'#22c55e':'#f59e0b' }}/>{health?.status==='ok'?'Connected':'Loading'} • {health?.['marts.mart_daily_sales'] ?? '—'} rows</span>
            <a href="http://localhost:8000/docs" target="_blank" style={{ color:'#0ea5e9', textDecoration:'none', fontWeight:600, border:'1px solid #e0f2fe', background:'#f0f9ff', padding:'6px 10px', borderRadius:8 }}>API Docs</a>
          </div>
        </div>
      </div>

      <div style={{ maxWidth:1240, margin:'0 auto', padding:'16px 20px 32px' }}>
        {error && <div style={{ background:'#fef2f2', border:'1px solid #fecaca', color:'#991b1b', padding:12, borderRadius:8, marginBottom:12, fontSize:13 }}>{error}</div>}

        {/* Filters — single clean card */}
        <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:10, padding:12, display:'flex', gap:10, flexWrap:'wrap', alignItems:'end', marginBottom:12 }}>
          <div>
            <div style={{ fontSize:11, color:'#64748b', fontWeight:600, marginBottom:4 }}>Window</div>
            <select value={filters.days} onChange={e=> setFilters(s=>({...s, days:parseInt(e.target.value)}))} style={sel}>
              <option value={30}>Last 30 days</option><option value={60}>Last 60 days</option><option value={90}>Last 90 days</option><option value={180}>Last 180 days</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize:11, color:'#64748b', fontWeight:600, marginBottom:4 }}>Category</div>
            <select value={filters.category} onChange={e=> setFilters(s=>({...s, category:e.target.value, product_id:''}))} style={{...sel, minWidth:160}}>
              <option value="">All categories</option>{categories.map(c=> <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div style={{ flex:1, minWidth:240 }}>
            <div style={{ fontSize:11, color:'#64748b', fontWeight:600, marginBottom:4 }}>Product</div>
            <select value={filters.product_id} onChange={e=> setFilters(s=>({...s, product_id:e.target.value}))} style={{...sel, width:'100%'}}>
              <option value="">All products {filters.category?`in ${filters.category}`:''}</option>
              {products.filter(p=> !filters.category || p.category===filters.category).slice(0,80).map(p=> <option key={p.product_id} value={p.product_id}>#{p.product_id} — {p.product_name?.slice(0,50)}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize:11, color:'#64748b', fontWeight:600, marginBottom:4 }}>Horizon</div>
            <select value={filters.horizon} onChange={e=> setFilters(s=>({...s, horizon:parseInt(e.target.value)}))} style={sel}>
              <option value={7}>7 days</option><option value={14}>14 days</option><option value={30}>30 days</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize:11, color:'#64748b', fontWeight:600, marginBottom:4 }}>Threshold</div>
            <select value={filters.z} onChange={e=> setFilters(s=>({...s, z:parseFloat(e.target.value)}))} style={sel}>
              <option value={2}>z 2.0</option><option value={2.5}>z 2.5</option><option value={3}>z 3.0</option>
            </select>
          </div>
          <button onClick={()=> setFilters({days:90, category:'', product_id:'', horizon:30, z:2.5})} style={{ marginLeft:'auto', background:'#fff', border:'1px solid #e2e8f0', color:'#334155', padding:'8px 12px', borderRadius:8, fontSize:13, fontWeight:600, cursor:'pointer' }}>Reset</button>
        </div>

        {/* KPIs — flat, no gradients */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))', gap:10, marginBottom:12 }}>
          {[
            { label:'Revenue (30d)', value: kpis? `$${kpis.total_revenue.toLocaleString(undefined,{maximumFractionDigits:0})}`:'—', sub: kpis? `${kpis.total_days} days` : '' },
            { label:'Units sold (30d)', value: kpis? kpis.total_quantity.toLocaleString():'—', sub: kpis? `Avg ${Math.round(kpis.total_quantity/kpis.total_days)}/day` : '' },
            { label:'Avg daily revenue', value: kpis? `$${kpis.avg_daily_revenue.toFixed(0)}`:'—', sub:'30-day mean' },
            { label:'Top category', value: kpis?.top_category_by_revenue ?? '—', sub: kpis?.top_category_revenue? `$${Math.round(kpis.top_category_revenue).toLocaleString()}`:'' },
          ].map(k=>(
            <div key={k.label} style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:10, padding:14 }}>
              <div style={{ fontSize:11, color:'#64748b', fontWeight:600, letterSpacing:'.04em', textTransform:'uppercase' }}>{k.label}</div>
              <div style={{ fontSize:20, fontWeight:700, color:'#0f172a', marginTop:6 }}>{k.value}</div>
              <div style={{ fontSize:12, color:'#94a3b8', marginTop:2 }}>{k.sub}</div>
            </div>
          ))}
        </div>

        {/* Sales trend */}
        <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:10, padding:14, marginBottom:10 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:8 }}>
            <h3 style={{ fontSize:13, fontWeight:700, color:'#0f172a' }}>Sales trend {filters.category?`· ${filters.category}`:''} {filters.product_id?`· #${filters.product_id}`:''}</h3>
            <span style={{ fontSize:11, color:'#64748b' }}>{loading? 'Loading…' : `${trends.length} days`}</span>
          </div>
          <div style={{ height:260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends}>
                <CartesianGrid stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize:11, fill:'#64748b' }} axisLine={false} tickLine={false} minTickGap={28} tickFormatter={v=> v.slice(5)} />
                <YAxis tick={{ fontSize:11, fill:'#64748b' }} axisLine={false} tickLine={false} width={40} />
                <Tooltip content={<TooltipCard/>} />
                <Area type="monotone" dataKey="total_revenue" name="Revenue" stroke="#0ea5e9" fill="#e0f2fe" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="total_quantity" name="Units" stroke="#475569" fill="#f1f5f9" strokeWidth={1.5} dot={false} />
                <Legend wrapperStyle={{ fontSize:12 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Forecast */}
        <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:10, padding:14, marginBottom:10 }}>
          <div style={{ display:'flex', justifyContent:'space-between', gap:10, alignItems:'start' }}>
            <div>
              <h3 style={{ fontSize:13, fontWeight:700, color:'#0f172a' }}>Forecast <span style={{ fontWeight:400, color:'#64748b' }}>· Holt-Winters (p=7, 95% CI)</span></h3>
              <div style={{ fontSize:12, color:'#64748b', marginTop:2 }}>{filters.product_id?`Product #${filters.product_id}`: filters.category||'All categories (summed)' } · Confidence band = forecast ± 1.96σ</div>
            </div>
            <button onClick={()=>{
              const rows = combined.map(r=> `${r.date},${r.actual??''},${r.forecast??''},${r.lower??''},${r.upper??''}`).join('\n')
              const blob=new Blob(['date,actual,forecast,lower,upper\n'+rows],{type:'text/csv'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`forecast.csv`; a.click()
            }} style={{ background:'#fff', border:'1px solid #e2e8f0', color:'#334155', padding:'6px 10px', borderRadius:8, fontSize:12, fontWeight:600, cursor:'pointer', whiteSpace:'nowrap' }}>Export CSV</button>
          </div>
          <div style={{ height:340, marginTop:10 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={combined}>
                <CartesianGrid stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize:11, fill:'#64748b' }} axisLine={false} tickLine={false} minTickGap={22} tickFormatter={v=> v.slice(5)} />
                <YAxis tick={{ fontSize:11, fill:'#64748b' }} axisLine={false} tickLine={false} width={32} />
                <Tooltip content={<TooltipCard/>} />
                <Legend wrapperStyle={{ fontSize:12 }} />
                <Area type="monotone" dataKey="upper" stroke="none" fill="#fff7ed" />
                <Area type="monotone" dataKey="lower" stroke="none" fill="#ffffff" />
                <Line type="monotone" dataKey="actual" name="Actual" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="5 4" />
                {anomalyMarkers.length>0 && <Scatter data={anomalyMarkers} dataKey="actual" name="Anomaly" fill="#dc2626" />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Anomalies — clean table */}
        <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:10, overflow:'hidden' }}>
          <div style={{ padding:'12px 14px', borderBottom:'1px solid #e2e8f0', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <h3 style={{ fontSize:13, fontWeight:700 }}>Anomalies <span style={{ color:'#64748b', fontWeight:400 }}>· {anomalies.length} flagged (14-day rolling, |z|&gt;{filters.z})</span></h3>
            <span style={{ fontSize:11, color:'#64748b' }}>{loading? 'Loading…': `${anomalies.length} rows`}</span>
          </div>
          {anomalies.length===0 ? (
            <div style={{ padding:24, textAlign:'center', color:'#64748b', fontSize:13 }}>No anomalies in this window. Try a lower threshold or wider date range.</div>
          ) : (
            <div style={{ overflowX:'auto' }}>
              <table style={{ width:'100%', fontSize:13, borderCollapse:'collapse' }}>
                <thead style={{ background:'#f8fafc', color:'#64748b', textAlign:'left', fontSize:11 }}>
                  <tr><th style={{ padding:'8px 12px', fontWeight:600 }}>Date</th><th style={{ fontWeight:600 }}>Product</th><th style={{ fontWeight:600 }}>Category</th><th style={{ padding:'8px 12px', textAlign:'right', fontWeight:600 }}>Qty</th><th style={{ textAlign:'right', fontWeight:600 }}>Mean</th><th style={{ textAlign:'right', fontWeight:600 }}>z</th><th style={{ padding:'8px 12px', fontWeight:600 }}>Severity</th></tr>
                </thead>
                <tbody>
                  {anomalies.slice(0,40).map((a,i)=>(
                    <tr key={i} style={{ borderTop:'1px solid #f1f5f9' }}>
                      <td style={{ padding:'9px 12px', whiteSpace:'nowrap', color:'#334155' }}>{a.date.slice(0,10)}</td>
                      <td style={{ color:'#0f172a' }}><span style={{ color:'#64748b' }}>#{a.product_id}</span> {a.product_name?.slice(0,48)}</td>
                      <td style={{ color:'#475569' }}>{a.category}</td>
                      <td style={{ padding:'9px 12px', textAlign:'right', fontWeight:600 }}>{a.quantity}</td>
                      <td style={{ textAlign:'right', color:'#64748b' }}>{a.rolling_mean?.toFixed(1)}</td>
                      <td style={{ textAlign:'right', fontWeight:700, color: Math.abs(a.z_score)>3.5 ? '#dc2626' : '#d97706' }}>{a.z_score?.toFixed(2)}</td>
                      <td style={{ padding:'9px 12px' }}><span style={{ fontSize:11, fontWeight:700, padding:'2px 8px', borderRadius:99, background: a.severity==='high'?'#fef2f2':'#fffbeb', color: a.severity==='high'?'#991b1b':'#92400e', border: `1px solid ${a.severity==='high'?'#fecaca':'#fde68a'}` }}>{a.severity}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div style={{ marginTop:10, color:'#94a3b8', fontSize:11, textAlign:'center' }}>Warehouse: DuckDB • dbt staging → intermediate → marts • Forecast: ExponentialSmoothing(p=7) • Orchestration: Prefect</div>
      </div>
    </div>
  )
}

const sel = { background:'#fff', border:'1px solid #e2e8f0', borderRadius:8, padding:'8px 10px', fontSize:13, color:'#0f172a', minWidth:110 }
