import { useEffect, useState, useMemo } from 'react'
import {
  LineChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart, Scatter
} from 'recharts'
import { fetchHealth, fetchKpis, fetchTrends, fetchForecast, fetchAnomalies, fetchProducts, fetchCategories } from './api.js'

const cardStyle = { background:'#1a1d27', border:'1px solid #2a2f45', borderRadius:12, padding:16 }
const selectStyle = { background:'#0f1117', color:'#e6e8ee', border:'1px solid #2a2f45', borderRadius:8, padding:'6px 10px' }
const labelStyle = { fontSize:12, color:'#9aa0b5', marginBottom:4 }

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
    setLoading(true)
    setError('')
    const p = {}
    if(filters.category) p.category = filters.category
    if(filters.product_id) p.product_id = filters.product_id
    Promise.all([
      fetchKpis(30).then(setKpis).catch(()=>{}),
      fetchTrends({ days: filters.days, ...(filters.category?{category:filters.category}:{}), ...(filters.product_id?{product_id:filters.product_id}:{}) }).then(setTrends).catch(()=>setTrends([])),
      fetchForecast({ ...(filters.product_id?{product_id:filters.product_id}: filters.category?{category:filters.category}:{}), horizon: filters.horizon }).then(setForecast).catch(()=>setForecast({forecast:[],history:[]})),
      fetchAnomalies({ days: filters.days, z_threshold: filters.z, ...(filters.category?{category:filters.category}:{}), ...(filters.product_id?{product_id:filters.product_id}:{}) }).then(setAnomalies).catch(()=>setAnomalies([])),
    ]).finally(()=> setLoading(false))
  },[filters])

  const combined = useMemo(()=>{
    // Merge history + forecast for chart
    const hist = (forecast.history||[]).map(d=>({ date:d.date, actual:d.quantity, revenue:d.revenue }))
    const fc = (forecast.forecast||[]).map(d=>({ date:d.date, forecast:d.forecast, lower:d.lower, upper:d.upper }))
    // if no product/category selected, forecast may be multiple categories -> pick first
    // group by date if multiple categories: sum
    if(fc.length && fc[0].category && !filters.product_id && !filters.category){
      // aggregate by date
      const m = {}
      forecast.forecast.forEach(r=>{
        if(!m[r.date]) m[r.date]={date:r.date, forecast:0, lower:0, upper:0}
        m[r.date].forecast += r.forecast
        m[r.date].lower += r.lower
        m[r.date].upper += r.upper
      })
      const agg = Object.values(m).sort((a,b)=> a.date.localeCompare(b.date))
      return [...hist, ...agg]
    }
    return [...hist, ...fc]
  },[forecast, filters])

  const anomalyMarkers = useMemo(()=>{
    // map anomalies onto combined dates for scatter
    const map = new Map(combined.map(c=>[c.date, c]))
    return anomalies.map(a=>({ date:a.date, actual:a.quantity, z: a.z_score, severity:a.severity, product_id:a.product_id }))
      .filter(a=> map.has(a.date))
  },[anomalies, combined])

  return (
    <div style={{ maxWidth:1200, margin:'0 auto', padding:20 }}>
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
        <div>
          <h1 style={{ fontSize:22, fontWeight:700 }}>E-Commerce Demand Forecasting</h1>
          <p style={{ color:'#9aa0b5', fontSize:13, marginTop:4 }}>Sales trends • 30-day forecast (Holt-Winters, 95% CI) • anomaly flags • DuckDB + dbt + Prefect</p>
        </div>
        <div style={{ textAlign:'right', fontSize:12, color:'#9aa0b5' }}>
          <div>API: {health?.duckdb_exists ? '✓ DuckDB' : '…'} • {health?.['marts.mart_daily_sales'] ?? health?.['main.mart_daily_sales'] ?? ''} rows</div>
          <div><a href="http://localhost:8000/docs" target="_blank" style={{ color:'#6ea8fe' }}>API Docs</a> • <span style={{ color: health?.status==='ok'?'#4ade80':'#f87171' }}>{health?.status||'loading'}</span></div>
        </div>
      </header>

      {error && <div style={{ background:'#3a1a1a', padding:12, borderRadius:8, marginBottom:12, fontSize:13 }}>⚠️ {error} — is the API running at {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}?</div>}

      {/* Filters */}
      <div style={{ display:'flex', gap:12, flexWrap:'wrap', marginBottom:16, ...cardStyle, padding:12 }}>
        <div>
          <div style={labelStyle}>Date window</div>
          <select style={selectStyle} value={filters.days} onChange={e=> setFilters(f=>({...f, days:parseInt(e.target.value)}))}>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
          </select>
        </div>
        <div>
          <div style={labelStyle}>Category</div>
          <select style={selectStyle} value={filters.category} onChange={e=> setFilters(f=>({...f, category:e.target.value, product_id:''}))}>
            <option value="">All categories</option>
            {categories.map(c=> <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <div style={labelStyle}>Product</div>
          <select style={selectStyle} value={filters.product_id} onChange={e=> setFilters(f=>({...f, product_id:e.target.value}))}>
            <option value="">All products {filters.category?`in ${filters.category}`:''}</option>
            {products.filter(p=> !filters.category || p.category===filters.category).slice(0,50).map(p=> <option key={p.product_id} value={p.product_id}>#{p.product_id} {p.product_name?.slice(0,32)}</option>)}
          </select>
        </div>
        <div>
          <div style={labelStyle}>Horizon</div>
          <select style={selectStyle} value={filters.horizon} onChange={e=> setFilters(f=>({...f, horizon:parseInt(e.target.value)}))}>
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
          </select>
        </div>
        <div>
          <div style={labelStyle}>Anomaly z</div>
          <select style={selectStyle} value={filters.z} onChange={e=> setFilters(f=>({...f, z:parseFloat(e.target.value)}))}>
            <option value={2}>2.0 (sensitive)</option>
            <option value={2.5}>2.5 (default)</option>
            <option value={3}>3.0 (strict)</option>
          </select>
        </div>
        <div style={{ marginLeft:'auto', alignSelf:'flex-end', fontSize:12, color:'#9aa0b5' }}>{loading?'Loading…':`${trends.length} trend points • ${anomalies.length} anomalies`}</div>
      </div>

      {/* KPI cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))', gap:12, marginBottom:16 }}>
        {[
          {label:'Total Revenue (30d)', value: kpis? `$${kpis.total_revenue?.toLocaleString(undefined,{maximumFractionDigits:0})}`:'—'},
          {label:'Total Units (30d)', value: kpis? kpis.total_quantity?.toLocaleString():'—'},
          {label:'Avg Daily Revenue', value: kpis? `$${kpis.avg_daily_revenue?.toFixed(0)}`:'—'},
          {label:'Top Category', value: kpis?.top_category_by_revenue || '—', sub: kpis?.top_category_revenue? `$${kpis.top_category_revenue.toFixed(0)}`:''},
        ].map(k=>(
          <div key={k.label} style={cardStyle}>
            <div style={labelStyle}>{k.label}</div>
            <div style={{ fontSize:20, fontWeight:700 }}>{k.value}</div>
            {k.sub && <div style={{ fontSize:12, color:'#9aa0b5' }}>{k.sub}</div>}
          </div>
        ))}
      </div>

      {/* Trends chart */}
      <div style={{ ...cardStyle, marginBottom:16 }}>
        <h3 style={{ fontSize:14, marginBottom:8 }}>Sales Trend {filters.category?`• ${filters.category}`:''} {filters.product_id?`• #${filters.product_id}`:''}</h3>
        <div style={{ height:260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trends}>
              <CartesianGrid stroke="#23263a" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize:11, fill:'#9aa0b5' }} minTickGap={24} />
              <YAxis tick={{ fontSize:11, fill:'#9aa0b5' }} />
              <Tooltip contentStyle={{ background:'#1a1d27', border:'1px solid #2a2f45', borderRadius:8 }} />
              <Legend />
              <Line type="monotone" dataKey="total_quantity" name="Units" stroke="#6ea8fe" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="total_revenue" name="Revenue ($)" stroke="#4ade80" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Forecast chart with CI */}
      <div style={{ ...cardStyle, marginBottom:16 }}>
        <h3 style={{ fontSize:14, marginBottom:4 }}>Forecast (Holt-Winters, 95% CI) {filters.product_id?`• Product #${filters.product_id}`: filters.category? `• ${filters.category}`:'• All categories (sum)'}</h3>
        <p style={{ fontSize:12, color:'#9aa0b5', marginBottom:8 }}>Blue = history, orange = forecast, shaded = confidence band, red dots = anomalies flagged (z &gt; {filters.z})</p>
        <div style={{ height:320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={combined}>
              <CartesianGrid stroke="#23263a" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize:11, fill:'#9aa0b5' }} minTickGap={18} />
              <YAxis tick={{ fontSize:11, fill:'#9aa0b5' }} />
              <Tooltip contentStyle={{ background:'#1a1d27', border:'1px solid #2a2f45', borderRadius:8 }} />
              <Legend />
              <Area type="monotone" dataKey="upper" name="Upper CI" stroke="none" fill="#f59e0b" fillOpacity={0.12} legendType="none" />
              <Area type="monotone" dataKey="lower" name="Lower CI" stroke="none" fill="#ffffff" fillOpacity={0} legendType="none" />
              <Line type="monotone" dataKey="actual" name="Actual" stroke="#6ea8fe" dot={false} strokeWidth={2} connectNulls />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="6 3" />
              {anomalyMarkers.length>0 && <Scatter data={anomalyMarkers} dataKey="actual" name="Anomaly" fill="#ef4444" />}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Anomalies table */}
      <div style={cardStyle}>
        <h3 style={{ fontSize:14, marginBottom:8 }}>Anomaly Alerts ({anomalies.length})</h3>
        {anomalies.length===0 ? <div style={{ color:'#9aa0b5', fontSize:13 }}>No anomalies above threshold in this window. Try lowering z to 2.0 or widening days.</div> :
        <div style={{ overflowX:'auto' }}>
          <table style={{ width:'100%', fontSize:13, borderCollapse:'collapse' }}>
            <thead><tr style={{ color:'#9aa0b5', textAlign:'left', borderBottom:'1px solid #2a2f45' }}>
              <th style={{ padding:'6px 8px' }}>Date</th><th>Product</th><th>Category</th><th>Qty</th><th>Mean</th><th>z</th><th>Severity</th>
            </tr></thead>
            <tbody>
              {anomalies.slice(0,20).map((a,i)=>(
                <tr key={i} style={{ borderBottom:'1px solid #1f2336', background: a.severity==='high'?'#2a1a1a':'transparent' }}>
                  <td style={{ padding:'6px 8px' }}>{a.date}</td>
                  <td>#{a.product_id} {a.product_name?.slice(0,24)}</td>
                  <td>{a.category}</td>
                  <td>{a.quantity}</td>
                  <td>{a.rolling_mean?.toFixed(1)}</td>
                  <td style={{ color: Math.abs(a.z_score)>3.5?'#ef4444': Math.abs(a.z_score)>2.5?'#f59e0b':'#9aa0b5', fontWeight:700 }}>{a.z_score?.toFixed(2)}</td>
                  <td><span style={{ background: a.severity==='high'?'#ef4444': a.severity==='medium'?'#f59e0b':'#2a2f45', color:'#0f1117', padding:'2px 6px', borderRadius:6, fontSize:11, fontWeight:700 }}>{a.severity}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {anomalies.length>20 && <div style={{ fontSize:12, color:'#9aa0b5', marginTop:6 }}>Showing 20 of {anomalies.length}. Filter by product/category to narrow.</div>}
        </div>
        }
      </div>

      <footer style={{ marginTop:20, color:'#6b7280', fontSize:12, textAlign:'center' }}>
        DuckDB {health?.duckdb_path} • dbt staging→marts • Holt-Winters (period=7) • Prefect daily 02:00 UTC • Swap to BigQuery via <code>warehouse/profiles.yml</code>
      </footer>
    </div>
  )
}
