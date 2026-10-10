from pathlib import Path
from html import escape
import base64
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='ANAC | Aviation Analytics 2024', layout='wide', initial_sidebar_state='expanded')
ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'DuLieu_DaXuLy'
LOGO = ROOT / 'assets' / 'anac_logo.png'
BLUE, ORANGE = '#1689CF', '#F0A35D'
COLORS = {'Noi dia':BLUE,'Quoc te':ORANGE,'Nội địa':BLUE,'Quốc tế':ORANGE}
NAMES = {'Noi dia':'Nội địa','Quoc te':'Quốc tế'}
UNITS = {'Noi dia':'BRL','Quoc te':'USD'}

st.markdown('''
<style>
.stApp {background: #F2F7FC; color:#173F67}
.block-container {max-width:1660px;padding-top:0.8rem;padding-bottom:2rem}
section[data-testid="stSidebar"] {background:linear-gradient(170deg,#076AA9,#084E86 70%,#073E70);border:0}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] label {color:#F6FBFF!important}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#CFEBFA!important}
section[data-testid="stSidebar"] div[role="radiogroup"] label {background:rgba(255,255,255,.09);padding:12px;border-radius:13px;margin-bottom:6px;border:1px solid rgba(255,255,255,.14)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {background:rgba(255,255,255,.25);border-color:rgba(255,255,255,.55)}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"]>div {background:white;border-radius:11px}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] * {color:#173F67!important}
.brand {font-size:22px;font-weight:850;color:white}.brand-sub {font-size:12px;letter-spacing:1px;color:#D6EDFA;margin-top:3px}
.brand-logo {background:white;border-radius:15px;padding:9px;margin-bottom:12px;text-align:center}.brand-logo img {height:76px;max-width:100%;object-fit:contain}
.hero {background:linear-gradient(115deg,#FFFFFF,#E6F4FF);padding:23px 27px;border:1px solid #D8EAF6;border-radius:21px;box-shadow:0 8px 28px rgba(32,95,145,.06)}
.eyebrow {font-size:13px;letter-spacing:1.3px;font-weight:750;color:#1689CF}
.hero-title {font-size:clamp(22px,2.3vw,34px);font-weight:850;color:#143F68;line-height:1.25;margin:8px 0}
.hero-sub {font-size:16px;color:#61819E}
.section-title {font-size:21px;font-weight:800;color:#173F67;margin:19px 0 11px}
div[data-testid="stVerticalBlockBorderWrapper"] {background:#FFFFFF;border:1px solid #DDEAF5;border-radius:17px;box-shadow:0 6px 23px rgba(33,88,136,.05)}
div[data-testid="stMetric"] {background:white;border:1px solid #DBEAF6;border-radius:15px;padding:12px}
div[data-testid="stMetricLabel"] p {font-size:12px;color:#6D88A0}
div[data-testid="stMetricValue"] {color:#174D77}
.insight {background:linear-gradient(120deg,#E8F5FF,#F7FCFF);border:1px solid #D7EAF7;border-radius:14px;padding:14px;min-height:102px}
.insight .k {font-size:13px;color:#698AA5}.insight .v {font-size:21px;font-weight:800;color:#154B73;margin:7px 0}.insight .n {font-size:13px;color:#287FAF}
#MainMenu, footer {visibility:hidden}
/* Keep Streamlit header and sidebar reopening button functional.
   Hide only the Deploy button rather than the entire toolbar. */
[data-testid="stHeader"] {display:flex!important;visibility:visible!important;background:transparent!important;height:3rem!important}
[data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapseButton"] {visibility:visible!important;opacity:1!important}
[data-testid="stDeployButton"] {display:none!important}
/* The navigation buttons in main area remain available even if sidebar is collapsed. */
.nav-caption {font-size:12px;color:#5D7F9C;font-weight:700;letter-spacing:.5px}

/* Increase text readability in the dashboard */
div[data-testid="stMarkdownContainer"] p {font-size:15px}
div[data-testid="stCaptionContainer"] p {font-size:13px}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {font-size:14px!important}
section[data-testid="stSidebar"] div[role="radiogroup"] label {font-size:14px}
div[data-testid="stMetricLabel"] p {font-size:14px}
div[data-testid="stMetricValue"] {font-size:29px}

</style>
''',unsafe_allow_html=True)

def read_csv(name):
    path = DATA / name
    with path.open('r',encoding='utf-8-sig') as f: head=f.readline()
    sep=';' if head.count(';')>head.count(',') else ','
    return pd.read_csv(path,sep=sep,encoding='utf-8-sig',low_memory=False)

@st.cache_data(show_spinner='Đang tải dữ liệu ANAC...')
def load():
    month=read_csv('tong_hop_theo_thang_2024.csv')
    nd=read_csv('top100_noi_dia_toa_do.csv'); nd['LOAI']='Nội địa'
    qt=read_csv('top100_quoc_te_toa_do.csv'); qt['LOAI']='Quốc tế'
    routes=pd.concat([nd,qt],ignore_index=True)
    for c in ['SO_GHE_BAN','GIA_BINH_QUAN']:
        month[c]=pd.to_numeric(month[c],errors='coerce')
    month['THANG']=month['THANG'].astype(str).str.strip()
    month['LOAI_CHUYEN_BAY']=month['LOAI_CHUYEN_BAY'].astype(str).str.strip()
    month=month.dropna(subset=['SO_GHE_BAN','GIA_BINH_QUAN']).sort_values(['LOAI_CHUYEN_BAY','THANG'])
    for c in ['ASSENTOS','LAT_DI','LON_DI','LAT_DEN','LON_DEN']:
        routes[c]=pd.to_numeric(routes[c],errors='coerce')
    routes=routes.dropna(subset=['ASSENTOS','LAT_DI','LON_DI','LAT_DEN','LON_DEN']).sort_values(['LOAI','ASSENTOS'],ascending=[True,False])
    return month,routes

@st.cache_data(show_spinner='Đang tải bảng điểm đến...')
def load_destinations():
    d=read_csv('xu_huong_diem_den_2024.csv')
    d['THANG']=d['THANG'].astype(str).str.strip()
    for c in ['ASSENTOS','LAT','LON']:
        d[c]=pd.to_numeric(d[c],errors='coerce')
    return d

try:
    monthly,routes=load()
except Exception as e:
    st.error(f'Không đọc được dữ liệu: {e}');st.stop()
months=sorted(monthly['THANG'].unique().tolist())
if not months: st.error('Không có dữ liệu theo tháng.');st.stop()

with st.sidebar:
    if LOGO.exists():
        ext='png' if LOGO.suffix.lower()=='.png' else 'jpeg'
        encoded=base64.b64encode(LOGO.read_bytes()).decode('ascii')
        st.markdown(f'<div class="brand-logo"><img src="data:image/{ext};base64,{encoded}" alt="ANAC"></div>',unsafe_allow_html=True)
    else: st.markdown('<div class="brand">ANAC</div>',unsafe_allow_html=True)
    st.markdown('<div class="brand">ANAC Aviation Analytics</div><div class="brand-sub">BRAZIL AIRLINE DATA · 2024</div>',unsafe_allow_html=True)
    st.divider();st.markdown('**ĐIỀU HƯỚNG**')
    page=st.radio('Trang dashboard',['01  Tổng quan & Giá vé','02  Tuyến bay & Chuyên sâu','03  Xu hướng du lịch & Điểm đến'],label_visibility='collapsed',key='navigation')
    st.divider();st.markdown('**BỘ LỌC PHÂN TÍCH**')
    market=st.selectbox('Thị trường',['Cả hai','Nội địa','Quốc tế'])
    start,end=st.select_slider('Khoảng tháng',options=months,value=(months[0],months[-1]))
    if page.startswith('02'):
        top=st.selectbox('Số tuyến mỗi loại',[20,50,100],index=1,format_func=lambda x:f'Top {x}')
    else: top=50
    if page.startswith('03'):
        dest_top=st.selectbox('Số điểm đến hiển thị',[5,10,20],index=1,format_func=lambda x:f'Top {x}')
    else: dest_top=10
    st.divider();st.caption('Nguồn giá vé: ANAC Brazil 2024');st.caption('Tọa độ sân bay: OurAirports')

chosen=['Noi dia','Quoc te'] if market=='Cả hai' else ['Noi dia' if market=='Nội địa' else 'Quoc te']
selected=monthly[monthly['THANG'].between(start,end)&monthly['LOAI_CHUYEN_BAY'].isin(chosen)].copy()
history=monthly.copy();history['PCT_PRICE']=history.groupby('LOAI_CHUYEN_BAY')['GIA_BINH_QUAN'].pct_change(fill_method=None)*100
history['PCT_SEATS']=history.groupby('LOAI_CHUYEN_BAY')['SO_GHE_BAN'].pct_change(fill_method=None)*100
changes=history[history['THANG'].between(start,end)&history['LOAI_CHUYEN_BAY'].isin(chosen)].copy()
route_sel=routes if market=='Cả hai' else routes[routes['LOAI']==market]
route_sel=route_sel.groupby('LOAI',group_keys=False).head(top).copy()

def section(t): st.markdown(f'<div class="section-title">{escape(t)}</div>',unsafe_allow_html=True)
def plot(fig,key): st.plotly_chart(fig,width='stretch',config={'displaylogo':False},key=key)
def theme(fig,height=260,y=None):
    fig.update_layout(height=height,margin=dict(l=8,r=8,t=18,b=15),paper_bgcolor='white',plot_bgcolor='white',font=dict(color='#58768E',size=13),xaxis=dict(showgrid=False),yaxis=dict(title=y,showgrid=True,gridcolor='#EBF1F7'),hovermode='closest')
    return fig
def panel(title,sub,fig,key):
    with st.container(border=True):
        st.markdown('**'+title+'**');st.caption(sub);plot(fig,key)
def avg(d):
    total=d['SO_GHE_BAN'].sum()
    return float((d['GIA_BINH_QUAN']*d['SO_GHE_BAN']).sum()/total) if total>0 else None
def insight(label,value,note):
    st.markdown(f'<div class="insight"><div class="k">{escape(str(label))}</div><div class="v">{escape(str(value))}</div><div class="n">{escape(str(note))}</div></div>',unsafe_allow_html=True)

def line_chart(code,field):
    d=selected[selected['LOAI_CHUYEN_BAY']==code].sort_values('THANG')
    f=go.Figure(go.Scatter(x=d['THANG'],y=d[field],mode='lines+markers',line=dict(color=COLORS[code],width=2.7),marker=dict(size=6),hovertemplate='%{x}<br>%{y:,.2f}<extra></extra>'))
    return theme(f,255,UNITS[code] if field=='GIA_BINH_QUAN' else 'Số ghế')
def change_chart(code,field):
    d=changes[changes['LOAI_CHUYEN_BAY']==code].dropna(subset=[field]).sort_values('THANG')
    f=go.Figure(go.Bar(x=d['THANG'],y=d[field],marker_color=[BLUE if v>=0 else ORANGE for v in d[field]],hovertemplate='%{x}<br>%{y:+.2f}%<extra></extra>'))
    f.add_hline(y=0,line_color='#BFD0DF',line_width=1)
    return theme(f,235,'%')
def map_chart():
    f=go.Figure()
    for _,r in route_sel.iterrows():
        f.add_trace(go.Scattergeo(lon=[r['LON_DI'],r['LON_DEN']],lat=[r['LAT_DI'],r['LAT_DEN']],mode='lines',line=dict(color=COLORS[r['LOAI']],width=1),opacity=.45,hoverinfo='skip',showlegend=False))
    a=route_sel[['ORIGEM','TEN_DI','LAT_DI','LON_DI']].copy();a.columns=['CODE','NAME','LAT','LON']
    b=route_sel[['DESTINO','TEN_DEN','LAT_DEN','LON_DEN']].copy();b.columns=['CODE','NAME','LAT','LON']
    airports=pd.concat([a,b],ignore_index=True).drop_duplicates('CODE')
    f.add_trace(go.Scattergeo(lon=airports['LON'],lat=airports['LAT'],mode='markers',marker=dict(size=4,color='#21608B'),text=airports['CODE'],customdata=airports['NAME'],hovertemplate='<b>%{text}</b><br>%{customdata}<extra></extra>',name='Sân bay'))
    view=dict(projection=dict(type='mercator'),lataxis=dict(range=[-35,7]),lonaxis=dict(range=[-76,-32])) if market=='Nội địa' else dict(projection=dict(type='natural earth'),fitbounds='locations')
    f.update_layout(height=440,margin=dict(l=0,r=0,t=0,b=0),geo=dict(**view,showland=True,landcolor='#E7F0F8',showocean=True,oceancolor='#F7FBFE',showcountries=True,countrycolor='#C7D8E6',showcoastlines=True,coastlinecolor='#C7D8E6',showframe=False,bgcolor='white'),paper_bgcolor='white')
    return f,len(airports)
def top_chart():
    d=route_sel.nlargest(10,'ASSENTOS').sort_values('ASSENTOS').copy();d['NAME']=d['ORIGEM'].astype(str)+' → '+d['DESTINO'].astype(str)
    f=go.Figure(go.Bar(x=d['ASSENTOS'],y=d['NAME'],orientation='h',marker_color=[COLORS[v] for v in d['LOAI']],hovertemplate='%{y}<br>%{x:,.0f} ghế<extra></extra>'))
    return theme(f,340)
def share_chart():
    s=monthly[monthly['THANG'].between(start,end)].groupby('LOAI_CHUYEN_BAY')['SO_GHE_BAN'].sum()
    f=go.Figure(go.Pie(labels=['Nội địa','Quốc tế'],values=[s.get('Noi dia',0),s.get('Quoc te',0)],hole=.65,marker=dict(colors=[BLUE,ORANGE]),textinfo='percent',hovertemplate='%{label}<br>%{value:,.0f} ghế<extra></extra>'))
    f.update_layout(height=290,margin=dict(l=4,r=4,t=6,b=8),legend=dict(orientation='h',x=.5,xanchor='center',y=-.1),paper_bgcolor='white')
    return f
def scatter_chart(code):
    d=selected[selected['LOAI_CHUYEN_BAY']==code]
    f=go.Figure(go.Scatter(x=d['GIA_BINH_QUAN'],y=d['SO_GHE_BAN'],text=d['THANG'],mode='markers',marker=dict(size=9,color=COLORS[code]),hovertemplate='%{text}<br>Giá: %{x:,.2f}<br>Ghế: %{y:,.0f}<extra></extra>'))
    f=theme(f,285,'Số ghế bán');f.update_xaxes(title=f'Giá ({UNITS[code]})')
    r=d['GIA_BINH_QUAN'].corr(d['SO_GHE_BAN']) if len(d)>=3 else np.nan
    return f,r

def ranking_destinations(d, type_name, group_key, n):
    subset=d[d['LOAI']==type_name]
    if group_key=='DIA_DIEM':
        # City and country should be kept together to avoid name collisions.
        sub=subset.copy();sub['NHAN']=sub['DIA_DIEM'].fillna(sub['DESTINO'])+' ('+sub['QUOC_GIA'].fillna('?')+')'
    elif group_key=='QUOC_GIA':
        sub=subset.copy();sub['NHAN']=sub['QUOC_GIA'].fillna('Không rõ')
    else:
        sub=subset.copy();sub['NHAN']=sub['DESTINO']+' · '+sub['DIA_DIEM'].fillna(sub['DESTINO'])
    rank=sub.groupby('NHAN',as_index=False)['ASSENTOS'].sum().sort_values('ASSENTOS',ascending=False).head(n)
    return rank,sub

def ranking_chart(rank,color):
    v=rank.sort_values('ASSENTOS')
    f=go.Figure(go.Bar(x=v['ASSENTOS'],y=v['NHAN'],orientation='h',marker_color=color,hovertemplate='%{y}<br>%{x:,.0f} ghế<extra></extra>'))
    f.update_layout(height=max(270,len(v)*34+75),margin=dict(l=12,r=12,t=12,b=15),paper_bgcolor='white',plot_bgcolor='white',font=dict(color='#58768E',size=13),xaxis=dict(title='Ghế bán',gridcolor='#EBF1F7'),yaxis=dict(title=None,automargin=True))
    return f

def destination_month_chart(sub,rank):
    top_keys=rank['NHAN'].head(5).tolist();t=sub[sub['NHAN'].isin(top_keys)].groupby(['THANG','NHAN'],as_index=False)['ASSENTOS'].sum()
    f=go.Figure()
    for name in top_keys:
        x=t[t['NHAN']==name].sort_values('THANG')
        f.add_trace(go.Scatter(x=x['THANG'],y=x['ASSENTOS'],mode='lines+markers',name=name,marker=dict(size=5)))
    f=theme(f,460,'Ghế bán');f.update_layout(legend=dict(orientation='h',y=-.26,x=.5,xanchor='center',font=dict(size=12)),margin=dict(l=12,r=12,t=25,b=110))
    return f

def destinations_map(d,top_n):
    grouped=d.groupby(['DESTINO','DIA_DIEM','QUOC_GIA','LAT','LON','LOAI'],dropna=False,as_index=False)['ASSENTOS'].sum()
    selected_top=grouped.sort_values('ASSENTOS',ascending=False).groupby('LOAI',group_keys=False).head(top_n)
    selected_top=selected_top.dropna(subset=['LAT','LON'])
    f=go.Figure()
    for kind,g in selected_top.groupby('LOAI'):
        f.add_trace(go.Scattergeo(lat=g['LAT'],lon=g['LON'],mode='markers',marker=dict(size=5,color=COLORS[kind],opacity=.85),text=g['DIA_DIEM'].fillna(g['DESTINO']),hovertext=[f'{city} ({code})<br>{seats:,.0f} ghế' for city,code,seats in zip(g['DIA_DIEM'].fillna(g['DESTINO']),g['DESTINO'],g['ASSENTOS'])],hovertemplate='%{hovertext}<extra></extra>',name=kind))
    view=dict(projection=dict(type='mercator'),lataxis=dict(range=[-35,7]),lonaxis=dict(range=[-76,-32])) if market=='Nội địa' else dict(projection=dict(type='natural earth'),fitbounds='locations')
    f.update_layout(height=370,margin=dict(l=0,r=0,t=0,b=0),geo=dict(**view,showland=True,landcolor='#E7F0F8',showocean=True,oceancolor='#F7FBFE',showcountries=True,countrycolor='#C7D8E6',showcoastlines=True,coastlinecolor='#C7D8E6',showframe=False,bgcolor='white'),legend=dict(orientation='h',x=0,y=0),paper_bgcolor='white')
    return f

# Secondary navigation stays visible when the sidebar is collapsed.
# This avoids getting stuck on one page if the Streamlit sidebar toggle is hidden.
st.markdown('<div class="nav-caption">CHUYỂN TRANG NHANH</div>', unsafe_allow_html=True)
nav_labels = [
    '01  Tổng quan & Giá vé',
    '02  Tuyến bay & Chuyên sâu',
    '03  Xu hướng du lịch & Điểm đến',
]
nav_cols = st.columns(3, gap='small')
for nav_col, nav_label in zip(nav_cols, nav_labels):
    with nav_col:
        active = st.session_state.get('navigation', nav_labels[0]) == nav_label
        st.button(
            nav_label,
            key='quick_nav_' + nav_label[:2],
            width='stretch',
            type='primary' if active else 'secondary',
            on_click=lambda value=nav_label: st.session_state.update(navigation=value),
        )
st.write('')

# Use contiguous HTML to prevent the Markdown code-block rendering issue.
st.markdown('<div class="hero"><div class="eyebrow">ANAC AVIATION INTELLIGENCE | BRAZIL 2024</div><div class="hero-title">Phân tích biến động giá vé máy bay &amp; Xu hướng du lịch nội địa / quốc tế</div><div class="hero-sub">Phân tích giá vé, số ghế bán và mạng lưới tuyến bay nội địa / quốc tế tại Brazil năm 2024.</div></div>',unsafe_allow_html=True)

if page.startswith('01'):
    section('01 | Tổng quan thị trường')
    nd=selected[selected['LOAI_CHUYEN_BAY']=='Noi dia'];qt=selected[selected['LOAI_CHUYEN_BAY']=='Quoc te']
    k1,k2,k3=st.columns(3)
    k1.metric('TỔNG GHẾ BÁN',f"{selected['SO_GHE_BAN'].sum():,.0f}")
    p1,p2=avg(nd),avg(qt)
    k2.metric('GIÁ NỘI ĐỊA',f'{p1:,.2f} BRL' if p1 is not None else 'Không áp dụng')
    k3.metric('GIÁ QUỐC TẾ',f'{p2:,.2f} USD' if p2 is not None else 'Không áp dụng')
    section('02 | Xu hướng giá vé')
    for col,code in zip(st.columns(len(chosen)),chosen):
        with col:panel('Giá vé | '+NAMES[code],'Bình quân có trọng số theo ghế · '+UNITS[code],line_chart(code,'GIA_BINH_QUAN'),'price_'+code)
    section('03 | Biến động giá theo tháng')
    for col,code in zip(st.columns(len(chosen)),chosen):
        with col:panel('Biến động | '+NAMES[code],'So với tháng trước (%)',change_chart(code,'PCT_PRICE'),'change_'+code)
    section('04 | Số ghế bán theo tháng')
    for col,code in zip(st.columns(len(chosen)),chosen):
        with col:panel('Ghế bán | '+NAMES[code],'Tổng ghế bán theo tháng',line_chart(code,'SO_GHE_BAN'),'seat_'+code)
    section('05 | Phát hiện nổi bật')
    for code in chosen:
        d=selected[selected['LOAI_CHUYEN_BAY']==code]
        if d.empty:continue
        hi,lo,busy=d.loc[d['GIA_BINH_QUAN'].idxmax()],d.loc[d['GIA_BINH_QUAN'].idxmin()],d.loc[d['SO_GHE_BAN'].idxmax()]
        st.markdown('**'+NAMES[code]+'**')
        a,b,c=st.columns(3)
        with a:insight('GIÁ CAO NHẤT',f"{hi['GIA_BINH_QUAN']:,.2f} {UNITS[code]}",hi['THANG'])
        with b:insight('GIÁ THẤP NHẤT',f"{lo['GIA_BINH_QUAN']:,.2f} {UNITS[code]}",lo['THANG'])
        with c:insight('THÁNG BÁN NHIỀU GHẾ',f"{busy['SO_GHE_BAN']:,.0f}",busy['THANG'])

elif page.startswith('02'):
    section('01 | Mạng lưới tuyến bay ANAC')
    mc,ic=st.columns([2.5,1])
    with mc:
        f,n_air=map_chart();panel('Flight Route Network',f'{market} · Top {top} mỗi loại · Cả năm 2024',f,'route_map')
    with ic:
        st.metric('SỐ TUYẾN HIỂN THỊ',len(route_sel));st.metric('SỐ SÂN BAY',n_air);st.metric('GHẾ TRÊN CÁC TUYẾN',f"{route_sel['ASSENTOS'].sum():,.0f}")
        st.caption('Top tuyến dựa trên cả năm; bộ lọc tháng không áp dụng cho bản đồ.')
    section('02 | Xếp hạng tuyến bay và cơ cấu')
    a,b=st.columns([1.5,1])
    with a:panel('Top 10 tuyến bay','Xếp hạng theo số ghế bán năm 2024',top_chart(),'top')
    with b:panel('Tỷ trọng ghế trong dữ liệu','Hai tập ANAC, không phải toàn thị trường',share_chart(),'share')
    section('03 | Biến động số ghế bán')
    for col,code in zip(st.columns(len(chosen)),chosen):
        with col:panel('Ghế bán | '+NAMES[code],'Thay đổi so với tháng trước (%)',change_chart(code,'PCT_SEATS'),'seat_change_'+code)
    section('04 | Mối quan hệ giữa giá vé và số ghế bán')
    for col,code in zip(st.columns(len(chosen)),chosen):
        fig,r=scatter_chart(code)
        with col:panel('Tương quan | '+NAMES[code],f'Pearson r = {r:.3f}' if pd.notna(r) else 'Không đủ dữ liệu',fig,'corr_'+code)
    section('05 | Dữ liệu chi tiết và tải xuống')
    with st.expander('Bảng dữ liệu theo tháng'):
        st.dataframe(selected,height=260,hide_index=True,width="stretch")
        st.download_button('Tải dữ liệu tháng CSV',selected.to_csv(index=False).encode('utf-8-sig'),'phan_tich_thang_2024.csv','text/csv')
    with st.expander('Danh sách tuyến bay'):
        cols=['LOAI','ORIGEM','DESTINO','ASSENTOS']
        st.dataframe(route_sel[cols],height=260,hide_index=True,width="stretch")
        st.download_button('Tải tuyến bay CSV',route_sel[cols].to_csv(index=False).encode('utf-8-sig'),'tuyen_bay_2024.csv','text/csv')

else:
    section('01 | Xu hướng lựa chọn điểm đến năm 2024')
    try:
        dest=load_destinations()
    except FileNotFoundError:
        st.warning('Chưa có dữ liệu điểm đến. Hãy chạy: python phan_tich_diem_den.py');st.stop()
    except Exception as e:
        st.error(f'Lỗi đọc dữ liệu điểm đến: {e}');st.stop()
    dest=dest[dest['THANG'].between(start,end)].copy()
    if market!='Cả hai':dest=dest[dest['LOAI']==market].copy()
    st.caption('Xếp hạng dựa trên ghế bán và sân bay đến (DESTINO), không phải số khách du lịch thực tế. Chỉ xét quốc tế xuất phát từ Brazil.')
    if dest.empty:
        st.warning('Không có dữ liệu điểm đến với bộ lọc hiện tại.');st.stop()
    x1,x2,x3=st.columns(3)
    x1.metric('SỐ GHẾ TRONG DỮ LIỆU ĐIỂM ĐẾN',f"{dest['ASSENTOS'].sum():,.0f}")
    x2.metric('SỐ SÂN BAY ĐẾN',dest['DESTINO'].nunique())
    x3.metric('SỐ QUỐC GIA ĐẾN',dest['QUOC_GIA'].nunique())
    for market_name in ['Nội địa','Quốc tế']:
        if market!='Cả hai' and market!=market_name:continue
        subset=dest[dest['LOAI']==market_name]
        if subset.empty:continue
        section(('02' if market_name=='Nội địa' else '03')+' | Điểm đến '+market_name.lower()+' được mua vé nhiều')
        rank,prepared=ranking_destinations(dest,market_name,'DIA_DIEM',dest_top)
        col1,col2=st.columns([1,1.35])
        with col1:panel('Top điểm đến '+market_name.lower(),f'Top {dest_top} thành phố theo ghế bán',ranking_chart(rank,COLORS[market_name]),'dest_rank_'+market_name)
        with col2:panel('Xu hướng mua vé của Top 5', 'Theo tháng bán vé, không phải tháng khởi hành',destination_month_chart(prepared,rank),'dest_month_'+market_name)
        if market_name=='Quốc tế':
            rank_ctry,_=ranking_destinations(dest,market_name,'QUOC_GIA',10)
            panel('Top quốc gia điểm đến','Mã quốc gia ISO 3166-1 alpha-2',ranking_chart(rank_ctry,ORANGE),'countries_rank')
    section('04 | Bản đồ các điểm đến nổi bật')
    with st.container(border=True):
        st.caption('Chấm sân bay nhỏ 5 px. Rê chuột để xem tên điểm đến, mã sân bay và số ghế bán trong khoảng tháng đã chọn.')
        plot(destinations_map(dest,dest_top),'destination_map')
    with st.expander('Bảng chi tiết điểm đến và tải CSV'):
        result=dest.sort_values('ASSENTOS',ascending=False)
        st.dataframe(result,height=290,hide_index=True,width="stretch")
        st.download_button('Tải dữ liệu điểm đến CSV',result.to_csv(index=False).encode('utf-8-sig'),'diem_den_2024.csv','text/csv')
    st.caption('Giới hạn: tháng là tháng bán vé; ghế bán không xác nhận số hành khách thực đi hay mục đích du lịch. Danh sách quốc tế chỉ gồm hành trình có sân bay xuất phát tại Brazil và sân bay đến ở nước ngoài, đối chiếu theo OurAirports.')

st.divider()
st.caption('Nguồn: ANAC Brazil 2024 và OurAirports. Giá nội địa (BRL) và quốc tế (USD) không so sánh trực tiếp. Phạm vi hai bộ dữ liệu ANAC có thể khác nhau. Bản đồ kết nối không phản ánh đường bay thực tế.')
