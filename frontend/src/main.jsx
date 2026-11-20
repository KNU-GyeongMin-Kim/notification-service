import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Bell, Monitor, Bookmark, BookmarkCheck, CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Clock3, GraduationCap, LayoutDashboard, LogIn, LogOut, Menu, Search, Settings2, Sparkles, X } from 'lucide-react';
import './styles.css';

const notices = [
  { id: 1, category: '장학', title: '2026학년도 2학기 국가장학금 2차 신청 안내', source: '학생지원팀', date: '2026.11.14', deadline: '2026.11.27', badge: 'D-11', color: 'violet', summary: '한국장학재단에서 2학기 국가장학금 2차 신청을 받습니다. 재학생, 신입생, 편입생 모두 신청할 수 있으며 가구원 정보 제공 동의도 함께 완료해 주세요.', important: true },
  { id: 2, category: '학사', title: '2026학년도 겨울 계절학기 수강 신청 안내', source: '학사관리팀', date: '2026.11.13', deadline: '2026.11.20', badge: 'D-4', color: 'blue', summary: '겨울 계절학기 수강 신청 및 등록 일정을 안내합니다. 수강 신청은 학사 포털에서 진행하며, 수강 인원에 따라 강의가 폐강될 수 있습니다.', important: true },
  { id: 3, category: '취업', title: '네이버클라우드 AI 엔지니어 인턴십 채용 설명회', source: '대학일자리센터', date: '2026.11.12', deadline: '2026.11.22', badge: 'D-6', color: 'mint', summary: 'AI 엔지니어 직무와 인턴십 전형을 소개하는 온라인 설명회입니다. 사전 신청자에게 참여 링크가 이메일로 발송됩니다.' },
  { id: 4, category: '행사', title: '컴퓨터공학과 오픈소스 프로젝트 전시회', source: '컴퓨터공학과', date: '2026.11.11', summary: '학생들이 한 학기 동안 개발한 오픈소스 프로젝트를 소개합니다. 재학생 누구나 자유롭게 관람하고 개발자들과 이야기를 나눌 수 있습니다.' },
  { id: 5, category: '대학원', title: '2027학년도 전기 대학원 신입생 모집', source: '대학원 교학팀', date: '2026.11.10', deadline: '2026.12.02', badge: 'D-16', color: 'orange', summary: '일반대학원 석사·박사 과정 신입생을 모집합니다. 온라인 원서 접수 후 제출 서류를 기한 내 우편 또는 방문 제출해 주세요.' },
  { id: 6, category: '학사', title: '2026학년도 2학기 성적 열람 및 이의 신청 기간', source: '학사관리팀', date: '2026.11.09', summary: '성적 열람 및 이의 신청 기간을 안내합니다. 이의 신청은 담당 교과목 교수님께 직접 문의해 주세요.' },
  { id: 7, category: '장학', title: '교내 근로장학생 2차 모집 안내', source: '학생지원팀', date: '2026.11.08', deadline: '2026.11.19', badge: 'D-3', color: 'violet', summary: '교내 부서에서 근무할 2학기 근로장학생을 추가 모집합니다. 신청 자격과 근무 시간은 상세 공지에서 확인해 주세요.' },
  { id: 8, category: '행사', title: '2026 동계 글로벌 현장학습 참가자 모집', source: '국제교류팀', date: '2026.11.07', deadline: '2026.11.25', badge: 'D-9', color: 'mint', summary: '해외 산업 현장과 문화를 경험할 글로벌 현장학습 참가자를 모집합니다. 프로그램 비용과 지원 자격을 확인한 뒤 지원해 주세요.' },
  { id: 9, category: '취업', title: '포트폴리오 완성 실전 워크숍 신청 안내', source: '대학일자리센터', date: '2026.11.06', summary: '현직자와 함께 나만의 포트폴리오를 완성하는 워크숍입니다. 선착순 마감될 수 있으니 빠르게 신청해 주세요.' },
  { id: 10, category: '학사', title: '2027학년도 1학기 전과 및 전공 변경 신청', source: '학사관리팀', date: '2026.11.05', deadline: '2026.11.30', badge: 'D-14', color: 'blue', summary: '전과와 전공 변경 신청을 접수합니다. 신청 전 학과별 선발 기준과 이수 학점 요건을 확인해 주세요.' },
];
const primaryCategories = ['\uC804\uCCB4', '\uC77C\uBC18\uACF5\uC9C0', '\uD559\uC0AC', '\uC7A5\uD559', '\uC2EC\uCEF4', '\uCCA8\uCEF4', '\uC778\uCEF4', '\uAE00\uC19D', '\uD50C\uC19D[\uAD6C.\uC2EC\uCEF4]', 'ICT\uC735\uD569[\uD559\uBD80]'];
const detailCategories = ['\uCDE8\uC5C5\u00B7\uC778\uD134', '\uC5F0\uAD6C', '\uD589\uC0AC\u00B7\uD504\uB85C\uADF8\uB7A8', '\uD574\uC678\u00B7\uAD50\uB958', '\uC77C\uBC18', '\uD559\uC0AC', '\uC7A5\uD559', '\uACF5\uBAA8\uC804\u00B7\uB300\uD68C'];
const categoryAssignment = { 1: ['\uC7A5\uD559', '\uC7A5\uD559'], 2: ['\uD559\uC0AC', '\uD559\uC0AC'], 3: ['\uC77C\uBC18\uACF5\uC9C0', '\uCDE8\uC5C5\u00B7\uC778\uD134'], 4: ['\uC2EC\uCEF4', '\uD589\uC0AC\u00B7\uD504\uB85C\uADF8\uB7A8'], 5: ['\uC77C\uBC18\uACF5\uC9C0', '\uC5F0\uAD6C'], 6: ['\uCCA8\uCEF4', '\uD559\uC0AC'], 7: ['\uC778\uCEF4', '\uCDE8\uC5C5\u00B7\uC778\uD134'], 8: ['\uC77C\uBC18\uACF5\uC9C0', '\uD574\uC678\u00B7\uAD50\uB958'], 9: ['\uAE00\uC19D', '\uACF5\uBAA8\uC804\u00B7\uB300\uD68C'], 10: ['\uD50C\uC19D[\uAD6C.\uC2EC\uCEF4]', '\uD559\uC0AC'] };
const categories = primaryCategories;
const StoreContext = createContext(null);
const useStore = () => useContext(StoreContext);
const formatDate = (value) => value?.replaceAll('.', '. ');
const daysUntil = (value) => {
  if (!value) return null;
  const [year, month, day] = value.split('.').map(Number);
  const deadline = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((deadline.getTime() - today.getTime()) / 86400000);
};
const deadlineLabel = (value) => {
  const days = daysUntil(value);
  return days === null ? '' : days < 0 ? '\uB9C8\uAC10' : `D-${days}`;
};
const isUrgentDeadline = (value) => {
  const days = daysUntil(value);
  return days !== null && days >= 0 && days <= 3;
};

function StoreProvider({ children }) {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('moabom-user') || 'null'));
  const [saved, setSaved] = useState(() => JSON.parse(localStorage.getItem('moabom-saved') || '[]'));
  const [read, setRead] = useState(() => JSON.parse(localStorage.getItem('moabom-read') || '[]'));
  const [prefs, setPrefs] = useState(() => JSON.parse(localStorage.getItem('moabom-prefs') || '{"channels":["앱"],"keywords":"장학금, 인턴, AI"}'));
  const [toast, setToast] = useState('');
  useEffect(() => { localStorage.setItem('moabom-user', JSON.stringify(user)); }, [user]);
  useEffect(() => { localStorage.setItem('moabom-saved', JSON.stringify(saved)); }, [saved]);
  useEffect(() => { localStorage.setItem('moabom-read', JSON.stringify(read)); }, [read]);
  useEffect(() => { localStorage.setItem('moabom-prefs', JSON.stringify(prefs)); }, [prefs]);
  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };
  const toggleSaved = (id) => setSaved((items) => items.includes(id) ? items.filter((x) => x !== id) : [...items, id]);
  const markRead = (id) => setRead((items) => items.includes(id) ? items : [...items, id]);
  return <StoreContext.Provider value={{ user, setUser, saved, toggleSaved, read, markRead, prefs, setPrefs, notify, toast }}>{children}</StoreContext.Provider>;
}

function App() {
  return <BrowserRouter><StoreProvider><AppShell /></StoreProvider></BrowserRouter>;
}

function AppShell() {
  const { user, read, toast } = useStore();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  useEffect(() => { setMenuOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }); }, [location.pathname]);
  return <div className="app-shell">
    <header className="topbar"><div className="topbar-inner">
      <Link to="/" className="brand"><span className="brand-mark"><GraduationCap size={22} /></span><span>모아봄<span className="brand-dot">.</span></span></Link>
      <nav className={`main-nav ${menuOpen ? 'open' : ''}`} aria-label="주 메뉴">
        <NavLink to="/" end>홈</NavLink><NavLink to="/notices">공지사항</NavLink>
        <NavLink to={user ? '/settings' : '/login'}>알림 설정</NavLink>
      </nav>
      <div className="header-actions">
        <div className="notification-wrap"><button className="icon-button notification-button" onClick={() => setNotificationsOpen((v) => !v)} aria-label="알림 목록" aria-expanded={notificationsOpen}>
          <Bell size={19} />{read.length < 4 && <span className="notification-dot" />}
        </button>{notificationsOpen && <NotificationPopover onClose={() => setNotificationsOpen(false)} />}</div>
        {user ? <Link to="/settings" className="user-chip"><span className="avatar">{user.name?.slice(0, 1) || '원'}</span><span className="user-name">{user.name}님</span><ChevronDown size={14} /></Link> : <Link to="/login" className="button button-primary header-login"><LogIn size={16} /> 로그인</Link>}
        <button className="icon-button menu-toggle" onClick={() => setMenuOpen((v) => !v)} aria-label="메뉴 열기">{menuOpen ? <X size={20} /> : <Menu size={20} />}</button>
      </div>
    </div></header>
    <main className="main-content"><Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/notices" element={<NoticeListPage />} />
      <Route path="/notices/:id" element={<NoticeDetailPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes></main>
    <Footer />
    {toast && <div className="toast" role="status"><span className="toast-check"><Check size={14} /></span>{toast}</div>}
  </div>;
}

function NotificationPopover({ onClose }) {
  const { read, markRead } = useStore();
  const navigate = useNavigate();
  const items = [notices[0], notices[1], notices[2], notices[4]];
  return <div className="notification-popover"><div className="notification-popover-head"><div><b>알림</b><span>{items.filter((n) => !read.includes(n.id)).length}개의 새 소식</span></div><button onClick={() => items.forEach((n) => markRead(n.id))}>모두 읽음</button></div>{items.map((notice) => <button className={`notification-item ${read.includes(notice.id) ? 'is-read' : ''}`} key={notice.id} onClick={() => { markRead(notice.id); onClose(); navigate(`/notices/${notice.id}`); }}><span className={`notification-item-icon ${notice.color}`}><Bell size={14} /></span><span className="notification-item-copy"><b>{notice.title}</b><small>{notice.source} · {notice.date}</small></span>{!read.includes(notice.id) && <i />}</button>)}<Link to="/notices" className="notification-all" onClick={onClose}>공지사항 전체 보기 <ChevronRight size={13} /></Link></div>;
}

function Footer() {
  return <footer className="footer"><div className="footer-inner"><Link to="/" className="brand footer-brand"><span className="brand-mark"><GraduationCap size={19} /></span><span>모아봄<span className="brand-dot">.</span></span></Link><p>학교 소식, 한눈에 모아봄.</p><span className="copyright">© 2026 모아봄. 학생들의 더 나은 캠퍼스 생활을 위해.</span></div></footer>;
}

function Eyebrow({ children }) { return <div className="eyebrow"><span className="eyebrow-line" />{children}</div>; }
function SectionHeading({ eyebrow, title, description, action }) { return <div className="section-heading"><div><Eyebrow>{eyebrow}</Eyebrow><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>; }
function NoticeCard({ notice, compact = false }) {
  const { saved, toggleSaved } = useStore();
  const navigate = useNavigate();
  return <article className={`notice-card ${compact ? 'compact' : ''}`} onClick={(event) => { if (event.target.closest('a, button')) return; navigate(`/notices/${notice.id}`); }}>
    <div className="card-topline"><span className={`category-pill ${notice.color || 'blue'}`}>{categoryAssignment[notice.id]?.[0] || notice.category}</span><span className="card-date">{formatDate(notice.date)}</span></div>
    <Link className="card-title" to={`/notices/${notice.id}`}>{notice.title}</Link>
    <p className="card-summary">{notice.summary}</p>
    <div className="card-bottom"><span className="source-name">{notice.source}</span><div className="card-meta">{notice.deadline && <span className={`deadline ${isUrgentDeadline(notice.deadline) ? 'urgent' : ''}`}><Clock3 size={12} /> {deadlineLabel(notice.deadline)}</span>}<button className={`save-button ${saved.includes(notice.id) ? 'is-saved' : ''}`} onClick={() => toggleSaved(notice.id)} aria-label={saved.includes(notice.id) ? '저장 취소' : '공지 저장'}>{saved.includes(notice.id) ? <BookmarkCheck size={17} /> : <Bookmark size={17} />}</button></div></div>
  </article>;
}

function HomePage() {
  const { user } = useStore();
  const urgent = notices.filter((n) => n.id !== 5 && n.deadline).slice(0, 3);
  return <>
    <section className="hero"><div className="hero-inner"><div className="hero-copy"><div className="hero-kicker"><Sparkles size={14} /> CAMPUS NOTICE, ALL IN ONE</div><h1>학교 소식,<br /><span>한눈에 모아봄.</span></h1><p>흩어져 있던 학과 공지사항을 한곳에 모았어요.<br className="desktop-break" /> 중요한 소식, 이제 놓치지 마세요.</p><div className="hero-actions"><Link to="/notices" className="button button-dark">공지사항 둘러보기 <ChevronRight size={17} /></Link><Link to={user ? '/settings' : '/login'} className="button button-plain">알림 설정하기 <Bell size={16} /></Link></div><div className="hero-social-proof"><div className="avatar-stack"><span>🎓</span><span>📚</span><span>✨</span></div><span>오늘도 <strong>새 공지 12개</strong>를 모아봤어요</span></div></div><div className="hero-visual"><div className="hero-decoration deco-one" /><div className="hero-decoration deco-two" /><div className="hero-board"><div className="board-top"><span className="board-live"><i /> LIVE UPDATE</span><span className="board-date">11월 16일 월요일</span></div><div className="board-message"><div className="board-greeting">좋은 하루예요, {user?.name || '원중'}님 <span>☀️</span></div><div className="board-stats"><div><strong>12<span>개</span></strong><small>오늘의 새 공지</small></div><span className="stats-divider" /><div><strong>03<span>개</span></strong><small>마감 임박</small></div></div><div className="board-progress"><div className="progress-label"><span>오늘 공지 수집</span><b>12 / 15</b></div><div className="progress-track"><i /></div></div></div><div className="board-section-head"><strong>놓치면 아쉬운 공지</strong><Link to="/notices">전체 보기 <ChevronRight size={13} /></Link></div>{urgent.slice(0, 2).map((n) => <Link to={`/notices/${n.id}`} className="board-notice" key={n.id}><span className={`board-icon ${n.color}`}><CalendarDays size={15} /></span><span className="board-notice-copy"><b>{n.title}</b><small>{n.source} · {n.badge} 마감</small></span><ChevronRight size={16} className="board-chevron" /></Link>)}</div><div className="floating-note"><span className="floating-icon"><Sparkles size={16} /></span><span><b>AI가 요약했어요</b><small>핵심만 빠르게 확인하세요</small></span></div></div></div></section>
    <section className="content-section home-notices"><div className="content-wrap"><SectionHeading eyebrow="LATEST NOTICES" title="지금 확인해야 할 공지" description="마감이 다가오는 소식부터 챙겨봤어요." action={<Link className="text-link" to="/notices">공지 전체 보기 <ChevronRight size={15} /></Link>} /><div className="notice-grid three-col">{urgent.map((n) => <NoticeCard key={n.id} notice={n} compact />)}</div></div></section>
    <section className="feature-strip"><div className="content-wrap feature-inner"><span className="feature-sparkle"><Sparkles size={23} /></span><div><strong>필요한 소식만, 놓치지 않도록</strong><p>관심 키워드를 설정하면 새로운 공지를 바로 알려드려요.</p></div><Link to={user ? '/settings' : '/login'} className="button button-white">내 알림 설정하기 <ChevronRight size={16} /></Link></div></section>
  </>;
}

function NoticeListPage() {
  const [category, setCategory] = useState(primaryCategories[0]);
  const [detailCategory, setDetailCategory] = useState('');
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('recent');
  const { saved } = useStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const showSaved = searchParams.get('filter') === 'saved';
  const filtered = useMemo(() => notices
    .filter((n) => n.id !== 5 && (!showSaved || saved.includes(n.id)) && (category === primaryCategories[0] || categoryAssignment[n.id]?.[0] === category) && (!detailCategory || categoryAssignment[n.id]?.[1] === detailCategory) && (n.title + n.summary + n.source).toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => {
      const dateValue = (value) => value ? new Date(value.replaceAll('.', '-')).getTime() : Number.POSITIVE_INFINITY;
      if (sort === 'deadline') return dateValue(a.deadline) - dateValue(b.deadline);
      return sort === 'oldest' ? dateValue(a.date) - dateValue(b.date) : dateValue(b.date) - dateValue(a.date);
    }), [category, detailCategory, query, sort, showSaved, saved]);
  const pageSize = 6; const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const items = filtered.slice((page - 1) * pageSize, page * pageSize);
  const selectCategory = (c) => { setCategory((current) => c === primaryCategories[0] || current === c ? primaryCategories[0] : c); setDetailCategory(''); setPage(1); };
  const selectDetailCategory = (c) => { setDetailCategory((old) => old === c ? '' : c); setPage(1); };
  const search = (e) => { e.preventDefault(); setQuery(draft.trim()); setPage(1); };
  return <div className="page-wrap list-page"><div className="page-intro"><Eyebrow>NOTICE BOARD</Eyebrow><h1>공지사항</h1><p>학교의 모든 소식을 한곳에서 확인해 보세요.</p></div>
    <div className="list-tools"><form className="search-box" onSubmit={search}><Search size={18} /><input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="궁금한 공지를 검색해 보세요" aria-label="공지 검색" /><button type="submit">검색</button></form><div className="list-tool-right"><button className={`saved-filter ${showSaved ? 'active' : ''}`} onClick={() => { setSearchParams(showSaved ? {} : { filter: 'saved' }); setPage(1); }}><Bookmark size={15} /> 저장한 공지 <span>{saved.length}</span></button><div className="sort-toggle" role="group" aria-label="정렬 기준"><button type="button" className={sort === 'recent' ? 'active' : ''} aria-pressed={sort === 'recent'} onClick={() => { setSort('recent'); setPage(1); }}>최신순</button><button type="button" className={sort === 'deadline' ? 'active' : ''} aria-pressed={sort === 'deadline'} onClick={() => { setSort('deadline'); setPage(1); }}>마감순</button><button type="button" className={sort === 'oldest' ? 'active' : ''} aria-pressed={sort === 'oldest'} onClick={() => { setSort('oldest'); setPage(1); }}>오래된순</button></div></div></div>
    <div className="category-tabs" role="tablist" aria-label="Notice categories">{categories.map((c) => { const count = c === primaryCategories[0] ? notices.length - 1 : notices.filter((n) => n.id !== 5 && categoryAssignment[n.id]?.[0] === c).length; return <button key={c} role="tab" aria-selected={category === c} className={category === c ? 'active' : ''} onClick={() => selectCategory(c)}>{c}<span>{count}</span></button>; })}</div>
    {category !== primaryCategories[0] && <div className="subcategory-tabs" role="group" aria-label="Subcategories">{detailCategories.map((c) => { const count = notices.filter((n) => n.id !== 5 && categoryAssignment[n.id]?.[0] === category && categoryAssignment[n.id]?.[1] === c).length; return <button type="button" key={c} className={detailCategory === c ? 'active' : ''} aria-pressed={detailCategory === c} onClick={() => selectDetailCategory(c)}>{c}<span>{count}</span></button>; })}</div>}
    <div className="results-caption"><span>{showSaved ? '저장한 공지 ' : ''}총 <strong>{filtered.length}개</strong>의 공지</span>{(query || showSaved) && <button onClick={() => { setDraft(''); setQuery(''); setSearchParams({}); }}>필터 지우기 <X size={13} /></button>}</div>
    {items.length ? <div className="notice-grid two-col">{items.map((n) => <NoticeCard key={n.id} notice={n} />)}</div> : <div className="empty-state"><span><Search size={24} /></span><h3>검색 결과가 없어요</h3><p>다른 검색어를 입력하거나 카테고리를 바꿔보세요.</p><button className="button button-outline" onClick={() => { setCategory(primaryCategories[0]); setDetailCategory(''); setDraft(''); setQuery(''); }}>전체 공지 보기</button></div>}
    {filtered.length > pageSize && <div className="pagination"><button aria-label="이전 페이지" disabled={page === 1} onClick={() => setPage(page - 1)}><ChevronLeft size={17} /></button>{Array.from({ length: pageCount }, (_, i) => <button key={i + 1} className={page === i + 1 ? 'active' : ''} onClick={() => setPage(i + 1)}>{i + 1}</button>)}<button aria-label="다음 페이지" disabled={page === pageCount} onClick={() => setPage(page + 1)}><ChevronRight size={17} /></button></div>}
  </div>;
}

function NoticeDetailPage() {
  const { id } = useParams(); const notice = notices.find((n) => n.id === Number(id)); const navigate = useNavigate();
  const { saved, toggleSaved, markRead, user } = useStore();
  useEffect(() => { if (notice) markRead(notice.id); }, [notice?.id]);
  if (!notice) return <NotFoundPage />;
  return <div className="page-wrap detail-page"><button className="back-link" onClick={() => navigate(-1)}><ChevronLeft size={17} /> 공지사항 목록</button><article className="detail-layout"><div className="detail-main"><div className="detail-kicker"><span className={`category-pill ${notice.color}`}>{notice.category}</span><span>{notice.source}</span><i /><span>{formatDate(notice.date)}</span></div><h1>{notice.title}</h1><div className="detail-actions"><button className={`button button-outline ${saved.includes(notice.id) ? 'saved-action' : ''}`} onClick={() => toggleSaved(notice.id)}>{saved.includes(notice.id) ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}{saved.includes(notice.id) ? '저장됨' : '공지 저장'}</button><button className="button button-outline" onClick={() => { navigator.clipboard?.writeText(window.location.href); }}><span>↗</span> 링크 공유</button></div><div className="detail-divider" />
      {notice.deadline && <div className="deadline-banner"><div className="deadline-icon"><Clock3 size={19} /></div><div><small>신청 마감까지</small><strong>{deadlineLabel(notice.deadline)} <span>· {formatDate(notice.deadline)} 마감</span></strong></div><Link to={user ? '/settings' : '/login'}>마감 알림 받기 <ChevronRight size={15} /></Link></div>}
      <section className="ai-summary"><div className="summary-heading"><span className="summary-sparkle"><Sparkles size={17} /></span><div><b>AI 핵심 요약</b><small>긴 공지도 핵심만 빠르게 확인해요</small></div><span className="ai-label">AI SUMMARY</span></div><p>{notice.summary}</p><div className="summary-points"><div><span>신청 대상</span><b>학부 재학생 및 해당 공지 대상자</b></div><div><span>신청 기간</span><b>{notice.deadline ? `${formatDate(notice.date)} ~ ${formatDate(notice.deadline)}` : '상세 공지에서 확인'}</b></div><div><span>신청 방법</span><b>학교 포털 온라인 신청</b></div></div></section>
      <div className="original-notice"><div className="original-heading"><h2>공지 원문</h2><span>원문 내용을 확인해 주세요</span></div><p>{notice.summary}</p><p>자세한 내용 및 신청 방법은 아래 원문 게시판에서 확인해 주시기 바랍니다. 신청을 희망하는 학생은 제출 서류와 일정을 확인한 후 기한 내에 신청해 주세요.</p><div className="notice-source-card"><span className="source-logo"><GraduationCap size={19} /></span><span><b>{notice.source}</b><small>학교 공식 공지사항</small></span><a href="https://www.google.com/search?q=%ED%95%99%EA%B5%90+%EA%B3%B5%EC%A7%80%EC%82%AC%ED%95%AD" target="_blank" rel="noreferrer">원문 게시판 방문 <ChevronRight size={14} /></a></div></div>
      <div className="detail-bottom"><Link to="/notices" className="button button-outline"><ChevronLeft size={15} /> 목록으로</Link><button className="button button-primary" onClick={() => { toggleSaved(notice.id); }}>관심 공지로 저장 <Bookmark size={15} /></button></div>
    </div><aside className="detail-aside"><div className="aside-card"><Eyebrow>NOTICE INFO</Eyebrow><h3>공지 정보</h3><dl><div><dt>카테고리</dt><dd>{notice.category}</dd></div><div><dt>게시일</dt><dd>{formatDate(notice.date)}</dd></div><div><dt>작성 부서</dt><dd>{notice.source}</dd></div>{notice.deadline && <div><dt>신청 마감</dt><dd className="aside-deadline">{formatDate(notice.deadline)}</dd></div>}</dl></div><div className="aside-help"><span><CircleHelp size={17} /></span><b>이런 공지를 더 받고 싶나요?</b><p>관심 키워드를 등록하고 맞춤 알림을 받아보세요.</p><Link to={user ? '/settings' : '/login'}>알림 설정하기 <ChevronRight size={14} /></Link></div></aside></article></div>;
}

function LoginPage() {
  const { setUser, notify } = useStore(); const navigate = useNavigate(); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [name, setName] = useState(''); const [showSignup, setShowSignup] = useState(false); const [error, setError] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const normalizedEmail = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) { setError('\uc62c\ubc14\ub978 \uc774\uba54\uc77c \uc8fc\uc18c\ub97c \uc785\ub825\ud574 \uc8fc\uc138\uc694.'); return; }
    if (password.length < 4) { setError('\ube44\ubc00\ubc88\ud638\ub97c 4\uc790 \uc774\uc0c1 \uc785\ub825\ud574 \uc8fc\uc138\uc694.'); return; }
    const accounts = JSON.parse(localStorage.getItem('moabom-accounts') || '[]');
    const account = accounts.find((item) => item.email === normalizedEmail);
    if (showSignup) {
      if (account) { setError('\uc774\ubbf8 \uac00\uc785\ub41c \uc774\uba54\uc77c\uc785\ub2c8\ub2e4. \ub85c\uadf8\uc778\ud574 \uc8fc\uc138\uc694.'); return; }
      const displayName = name.trim() || normalizedEmail.split('@')[0];
      const newAccount = { email: normalizedEmail, password, name: displayName };
      localStorage.setItem('moabom-accounts', JSON.stringify([...accounts, newAccount]));
      setUser({ email: newAccount.email, name: newAccount.name });
      notify(`${displayName}\ub2d8, \ubc18\uac00\uc6cc\uc694!`);
      navigate('/settings');
      return;
    }
    if (!account || account.password !== password) { setError('\uc774\uba54\uc77c \ub610\ub294 \ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.'); return; }
    setUser({ email: account.email, name: account.name });
    notify(`${account.name}\ub2d8, \ubc18\uac00\uc6cc\uc694!`);
    navigate('/settings');
  };
  return <div className="login-page"><div className="login-art"><div className="login-art-content"><Link to="/" className="brand login-brand"><span className="brand-mark"><GraduationCap size={22} /></span><span>모아봄<span className="brand-dot">.</span></span></Link><div className="login-quote"><span>“</span><h1>중요한 학교 소식,<br />놓치지 않도록.</h1><p>나에게 필요한 공지만 모아<br />편하게 받아보세요.</p></div><div className="login-illustration"><div className="ill-sun" /><div className="ill-paper"><span /><span /><span /><span /></div><div className="ill-book"><i /><i /><i /></div><div className="ill-flower">✳</div></div><div className="art-caption">학교 생활의 좋은 소식, 모아봄과 함께</div></div></div><div className="login-form-side"><div className="login-form-wrap"><div className="mobile-login-brand"><Link to="/" className="brand"><span className="brand-mark"><GraduationCap size={22} /></span><span>모아봄<span className="brand-dot">.</span></span></Link></div><Eyebrow>{showSignup ? 'JOIN MOABOM' : 'WELCOME BACK'}</Eyebrow><h2>{showSignup ? '모아봄 시작하기' : '다시 만났네요!'}</h2><p className="form-intro">{showSignup ? '간단한 정보로 계정을 만들고 소식을 모아보세요.' : '로그인하고 나에게 필요한 학교 소식을 확인해요.'}</p><form onSubmit={submit} className="auth-form">{showSignup && <label>이름<input value={name} onChange={(e) => setName(e.target.value)} placeholder="이름을 입력해 주세요" /></label>}<label>이메일 주소<div className="input-with-icon"><span>✉</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@university.ac.kr" autoComplete="email" /></div></label><label>비밀번호<div className="input-with-icon"><span>⌑</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="비밀번호를 입력해 주세요" autoComplete={showSignup ? 'new-password' : 'current-password'} /></div></label>{error && <p className="form-error">{error}</p>}<button className="button button-primary auth-submit" type="submit">{showSignup ? '계정 만들기' : '로그인'} <ChevronRight size={16} /></button></form><div className="auth-switch"><span>{showSignup ? '이미 계정이 있으신가요?' : '아직 계정이 없으신가요?'}</span><button onClick={() => { setShowSignup(!showSignup); setError(''); }}>{showSignup ? '로그인' : '회원가입'}</button></div><div className="login-note"><span><Check size={13} /></span>가입하면 맞춤 공지 알림을 설정할 수 있어요.</div></div></div></div>;
}

function SettingsPage() {
  const { user, setUser, setPrefs, prefs, notify } = useStore(); const navigate = useNavigate();
  const [keywordDraft, setKeywordDraft] = useState('');
  const addKeyword = (value) => {
    const keyword = value.trim().replace(/,$/, '');
    if (!keyword) return;
    setPrefs((old) => {
      const keywords = old.keywords.split(',').map((item) => item.trim()).filter(Boolean);
      return keywords.some((item) => item.toLowerCase() === keyword.toLowerCase()) ? old : { ...old, keywords: [...keywords, keyword].join(', ') };
    });
    setKeywordDraft('');
  };
  const hasKeyword = (keyword) => prefs.keywords.split(',').some((item) => item.trim().toLowerCase() === keyword.toLowerCase());
  const removeKeyword = (keyword) => setPrefs((old) => ({ ...old, keywords: old.keywords.split(',').map((item) => item.trim()).filter((item) => item && item !== keyword).join(', ') }));
  if (!user) return <LoginRedirect />;
  const channels = ['앱', '이메일', '문자'];
  const toggleChannel = (channel) => setPrefs((old) => ({ ...old, channels: old.channels.includes(channel) ? old.channels.filter((x) => x !== channel) : [...old.channels, channel] }));
  const save = (e) => { e.preventDefault(); notify('알림 설정을 저장했어요.'); };
  return <div className="page-wrap settings-page"><div className="page-intro"><Eyebrow>MY NOTIFICATIONS</Eyebrow><h1>알림 설정</h1><p>필요한 소식만 골라 편하게 받아보세요.</p></div><div className="settings-layout"><aside className="settings-profile"><div className="profile-avatar">{user.name?.slice(0, 1) || '원'}</div><strong>{user.name}님</strong><span>{user.email}</span><div className="profile-divider" /><button className="logout-button" onClick={() => { setUser(null); notify('로그아웃했어요.'); navigate('/'); }}><LogOut size={15} /> 로그아웃</button></aside><form className="settings-form" onSubmit={save}><div className="setting-card"><div className="setting-card-title"><span className="setting-icon"><Bell size={18} /></span><div><h2>알림 채널</h2><p>새 공지를 받아볼 방법을 선택해 주세요.</p></div></div><div className="channel-options">{channels.map((c, i) => <label className="channel-row" key={c}><span className={`channel-symbol channel-${i}`}>{i === 0 ? <Monitor size={17} /> : i === 1 ? '✉' : '▯'}</span><span className="channel-copy"><b>{c === '앱' ? '웹 알림' : c === '이메일' ? '이메일 알림' : '문자 알림'}</b><small>{c === '앱' ? '브라우저에서 새 소식을 알려드려요' : c === '이메일' ? user.email : '휴대폰 번호 등록 후 이용할 수 있어요'}</small></span><input type="checkbox" checked={prefs.channels.includes(c)} onChange={() => toggleChannel(c)} /><i className="custom-check"><Check size={12} /></i></label>)}</div><div className="setting-footnote"><CircleHelp size={14} /> 문자 알림은 추후 지원 예정이에요.</div></div><div className="setting-card"><div className="setting-card-title"><span className="setting-icon keyword-icon"><Search size={18} /></span><div><h2>관심 키워드</h2><p>키워드가 포함된 공지가 올라오면 알려드려요.</p></div></div><div className="keyword-label"><div className="keyword-label-heading"><span>알림 받을 키워드</span></div><div className="keyword-tag-editor"><div className="keyword-tags">{prefs.keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean).map((keyword) => <span className="keyword-tag" key={keyword}>{keyword}<button type="button" aria-label={`${keyword} 삭제`} onClick={() => removeKeyword(keyword)}><X size={14} /></button></span>)}<input className="keyword-tag-input" value={keywordDraft} onChange={(e) => setKeywordDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addKeyword(keywordDraft); } }} placeholder="키워드를 입력하고 Enter를 누르세요" /></div><button type="button" className="keyword-clear-button" disabled={!prefs.keywords.trim()} onClick={() => setPrefs((old) => ({ ...old, keywords: '' }))}>전체 삭제</button></div><small>Enter 또는 추가 버튼으로 태그를 추가하고, 태그의 ×를 눌러 삭제하세요.</small></div><div className="keyword-suggestions"><span>추천 키워드</span>{['장학금', '인턴', 'AI', '공모전'].map((k) => <button type="button" className={hasKeyword(k) ? 'selected' : ''} key={k} onClick={() => addKeyword(k)}>{k}{hasKeyword(k) && <Check size={11} />}</button>)}</div></div><div className="setting-card deadline-setting"><div className="setting-card-title"><span className="setting-icon deadline-setting-icon"><Clock3 size={18} /></span><div><h2>마감 알림</h2><p>신청 기한이 다가오는 공지를 다시 알려드려요.</p></div></div><label className="switch-row"><span><b>마감 임박 알림 받기</b><small>마감 3일 전에 알림을 보내드려요.</small></span><input type="checkbox" defaultChecked /><i className="switch-control" /></label></div><div className="settings-actions"><span><Settings2 size={14} /> 설정은 이 기기에 저장돼요.</span><button className="button button-primary" type="submit">설정 저장하기 <Check size={15} /></button></div></form></div></div>;
}

function LoginRedirect() { const location = useLocation(); const navigate = useNavigate(); useEffect(() => { navigate('/login', { replace: true, state: { from: location.pathname } }); }, []); return <div className="loading-route">로그인 페이지로 이동하고 있어요...</div>; }
function NotFoundPage() { return <div className="not-found"><span>404</span><h1>페이지를 찾을 수 없어요</h1><p>주소를 다시 확인하거나 홈으로 돌아가 주세요.</p><Link to="/" className="button button-primary">홈으로 돌아가기 <ChevronRight size={16} /></Link></div>; }

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
