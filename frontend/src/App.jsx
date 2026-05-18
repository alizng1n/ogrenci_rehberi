import { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, History, Library, Settings, 
  Send, Search, Plus, CheckCircle2, AlertTriangle, 
  FileText, ArrowRight, User, Users, Sun, Moon, Home,
  Upload, Camera, Check, X, FileCheck, Bell, Mail, ExternalLink,
  Clock, Info, Loader2, ChevronDown, ChevronUp, Inbox, Lock, LogOut, GraduationCap, Megaphone, Eye, EyeOff
} from 'lucide-react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './index.css';

function App() {
  const [isChatMode, setIsChatMode] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem('theme');
    return savedTheme !== null ? savedTheme === 'dark' : true;
  });
  const [stats, setStats] = useState({ total: 0, ready: 0, review: 0, efficiency: 0 });
  const [drafts, setDrafts] = useState([]);
  const [sources, setSources] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [personnel, setPersonnel] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dirSearch, setDirSearch] = useState('');
  const [dirDept, setDirDept] = useState('all');
  
  // Person Profile Modal State
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [personDetailLoading, setPersonDetailLoading] = useState(false);
  const [personDetail, setPersonDetail] = useState(null);
  const [activeAccordion, setActiveAccordion] = useState(null);

  // Zimbra E-Posta State
  const [zimbraEmail, setZimbraEmail] = useState(() => localStorage.getItem('zimbraEmail') || '');
  const [zimbraPassword, setZimbraPassword] = useState('');
  const [zimbraLoggedIn, setZimbraLoggedIn] = useState(false);
  const [zimbraLoading, setZimbraLoading] = useState(false);
  const [zimbraError, setZimbraError] = useState('');
  const [zimbraEmails, setZimbraEmails] = useState([]);
  const [zimbraStats, setZimbraStats] = useState({ total: 0, academic: 0, announcement: 0, unread: 0 });
  const [emailFilter, setEmailFilter] = useState('all'); // 'all' | 'academic' | 'announcement'
  const [showPassword, setShowPassword] = useState(false);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [emailDetailLoading, setEmailDetailLoading] = useState(false);

  const messagesEndRef = useRef(null);

  // Dilekçe Modal State
  const [isScanModalOpen, setIsScanModalOpen] = useState(false);
  const [activeSnippetId, setActiveSnippetId] = useState(null);

  // Petition Form States (with premium default values)
  const [fullname, setFullname] = useState('Ali Zengin');
  const [studentId, setStudentId] = useState('220301045');
  const [phone, setPhone] = useState('0555 123 45 67');
  const [department, setDepartment] = useState('Bilgisayar Mühendisliği');
  const [courseCode, setCourseCode] = useState('COM-202');
  const [courseName, setCourseName] = useState('Veritabanı Yönetim Sistemleri');
  const [reason, setReason] = useState('Sağlık Raporu / Hastalık Mazereti');
  const [dateRange, setDateRange] = useState('18.05.2026 - 20.05.2026');
  const [institution, setInstitution] = useState('İskenderun Devlet Hastanesi');
  const [petitionText, setPetitionText] = useState('');
  const [isEdited, setIsEdited] = useState(false);

  // Dynamic automatic petition compiler
  const handlePersonClick = async (person) => {
    setSelectedPerson(person);
    setIsProfileModalOpen(true);
    setPersonDetailLoading(true);
    setPersonDetail(null);
    setActiveAccordion(null);
    try {
      const res = await axios.get(`http://localhost:8000/api/person_detail?url=${encodeURIComponent(person.profile_url)}`);
      setPersonDetail(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setPersonDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!isEdited) {
      setPetitionText(
        `Fakülteniz/Yüksekokulunuz ${department} Bölümü ${studentId} numaralı öğrencisiyim. Öğrenim görmekte olduğum ${courseCode} kodlu ve '${courseName}' isimli dersin yarıyıl içi (vize) sınavına, ${dateRange} tarihlerini kapsayan ve ${institution} tarafından verilen ekteki mazeret belgemde (Tanı: ${reason}) belirtilen mazeretim nedeniyle katılamadım. Mevzuat gereğince ilgili ders için mazeret sınav hakkı tanınması hususunda gereğini ve bilgilerinizi saygılarımla arz ederim.`
      );
    }
  }, [fullname, studentId, phone, department, courseCode, courseName, reason, dateRange, institution, isEdited]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, draftsRes, sourcesRes, annRes, personnelRes] = await Promise.all([
          axios.get('http://localhost:8000/api/stats'),
          axios.get('http://localhost:8000/api/drafts'),
          axios.get('http://localhost:8000/api/sources'),
          axios.get('http://localhost:8000/api/announcements'),
          axios.get('http://localhost:8000/api/personnel')
        ]);
        setStats(statsRes.data);
        setDrafts(draftsRes.data);
        setSources(sourcesRes.data);
        setAnnouncements(annRes.data);
        const formatDept = (dept) => {
          if (!dept) return dept;
          const d = dept.trim().toUpperCase();
          if (d === 'BM') return 'Bilgisayar Müh.';
          if (d === 'MDBF') return 'Mühendislik Fak.';
          if (d === 'EE' || d === 'EEM') return 'Elektrik-Elektronik Müh.';
          if (d === 'İİBF' || d === 'IIBF') return 'İktisadi ve İdari Bil. Fak.';
          if (d === 'İME' || d === 'IME') return 'İşletme Müh.';
          if (d === 'MM') return 'Makine Müh.';
          if (d === 'İNM' || d === 'INM') return 'İnşaat Müh.';
          if (d === 'MAM') return 'Malzeme Müh.';
          if (d === 'MMF') return 'Mimarlık Fak.';
          return dept;
        };
        setPersonnel(personnelRes.data.map(p => ({ ...p, department: formatDept(p.department) })));
      } catch (err) {
        console.error("Failed to fetch data", err);
      }
    };
    fetchData();

    // Check Zimbra Session
    const checkZimbraSession = async () => {
      const savedEmail = localStorage.getItem('zimbraEmail');
      if (savedEmail) {
        try {
          const res = await axios.post('http://localhost:8000/api/zimbra/check-session', { email: savedEmail, password: '' });
          if (res.data.valid) {
            setZimbraLoggedIn(true);
          } else {
            localStorage.removeItem('zimbraEmail');
            setZimbraEmail('');
          }
        } catch (err) {
          console.error("Zimbra session check failed", err);
        }
      }
    };
    checkZimbraSession();
  }, []);

  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.remove('light-theme');
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.classList.add('light-theme');
      localStorage.setItem('theme', 'light');
    }
  }, [isDarkMode]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleStartChat = (initialMessage = '') => {
    setIsChatMode(true);
    if (initialMessage) {
      handleSendMessage(initialMessage);
    }
  };

  const handleSendMessage = async (customMessage) => {
    const textToSend = typeof customMessage === 'string' ? customMessage : input;
    if (!textToSend.trim()) return;

    // Add user message
    const newMessages = [...messages, { role: 'user', content: textToSend }];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/api/chat', {
        message: textToSend,
        history: messages
      });

      setMessages([...newMessages, { 
        role: 'assistant', 
        content: response.data.answer,
        sources: response.data.sources
      }]);
    } catch (error) {
      console.error(error);
      // Daha açıklayıcı bir hata mesajı göstermeye çalış
      let friendly = "Üzgünüm, bir hata oluştu. Lütfen sunucu bağlantısını kontrol edin.";
      if (error.response && error.response.data) {
        // Eğer backend özel bir cevap döndüyse onu göster
        const data = error.response.data;
        if (data.answer) {
          friendly = data.answer;
        } else if (data.detail) {
          friendly = `Sunucu hatası: ${data.detail}`;
        } else if (typeof data === 'string') {
          friendly = data;
        }
      } else if (error.message) {
        friendly = `Hata: ${error.message}`;
      }

      setMessages([...newMessages, { 
        role: 'assistant', 
        content: friendly
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleSaveAndDownloadPDF = async () => {
    // 1. Save draft to database
    try {
      await axios.post('http://localhost:8000/api/save-draft', {
        title: "Mazeret Sınavı Başvuru Dilekçesi",
        fullname,
        date_range: dateRange,
        reason,
        institution
      });
      
      // Refresh statistics and drafts list
      const [statsRes, draftsRes] = await Promise.all([
        axios.get('http://localhost:8000/api/stats'),
        axios.get('http://localhost:8000/api/drafts')
      ]);
      setStats(statsRes.data);
      setDrafts(draftsRes.data);
    } catch (err) {
      console.error("Failed to save draft", err);
    }
    
    // 2. Generate and download the PDF
    try {
      const response = await axios.post('http://localhost:8000/api/generate-pdf', {
        title: "Mazeret Sınavı Başvuru Dilekçesi",
        fullname,
        student_id: studentId,
        phone,
        department,
        course_code: courseCode,
        course_name: courseName,
        reason,
        date_range: dateRange,
        institution,
        petition_text: petitionText
      }, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = `iste_mazeret_dilekcesi_${studentId}.pdf`;
      link.click();
      
      // Reset state and close modal
      setIsScanModalOpen(false);
      setIsEdited(false);
    } catch (err) {
      console.error("PDF generation error", err);
      alert("PDF oluşturulurken bir hata oluştu. Lütfen tüm alanları doğru doldurduğunuzdan emin olun.");
    }
  };

  // Downloads the actual original source file (e.g. .docx or .pdf) directly from data/raw/
  const handleDownloadSourceFile = async (filename) => {
    try {
      const response = await axios.get(`http://localhost:8000/api/download-source`, {
        params: { filename },
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data]);
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      link.click();
    } catch (err) {
      console.error("Failed to download source file", err);
      alert("Dosya indirilirken bir hata oluştu. Lütfen sunucuda dosyanın mevcut olduğundan emin olun.");
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <h1>Öğrenci Rehberi</h1>
          <p>Başvuru ve Bilgi Sistemi</p>
        </div>

        {/* Home / Menu Button */}
        <button 
          className="nav-item" 
          style={{ 
            width: '100%', 
            border: '1px solid var(--border-color)', 
            background: !isChatMode && activeTab === 'dashboard' ? 'rgba(2, 132, 199, 0.1)' : 'transparent',
            color: !isChatMode && activeTab === 'dashboard' ? 'var(--text-primary)' : 'var(--text-secondary)',
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            padding: '10px 12px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '500',
            fontSize: '14px',
            marginBottom: '12px',
            transition: 'all 0.2s'
          }} 
          onClick={() => { setIsChatMode(false); setActiveTab('dashboard'); }}
        >
          <Home size={18} /> Menü (Ana Sayfa)
        </button>

        <button className="new-chat-btn" onClick={() => handleStartChat()} style={{ marginBottom: '12px' }}>
          <Plus size={18} />
          Soru Sor & Danış
        </button>

        {/* Directory Button */}
        <button 
          className="nav-item" 
          style={{ 
            width: '100%', 
            border: '1px solid var(--border-color)', 
            background: !isChatMode && activeTab === 'directory' ? 'rgba(2, 132, 199, 0.1)' : 'transparent',
            color: !isChatMode && activeTab === 'directory' ? 'var(--text-primary)' : 'var(--text-secondary)',
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            padding: '10px 12px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '500',
            fontSize: '14px',
            marginBottom: '12px',
            transition: 'all 0.2s'
          }} 
          onClick={() => { setIsChatMode(false); setActiveTab('directory'); }}
        >
          <Users size={18} /> Akademik Kadro
        </button>

        <button 
          className="nav-item" 
          style={{ 
            width: '100%', 
            border: '1px solid var(--border-color)', 
            background: 'transparent',
            color: 'var(--text-secondary)',
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            padding: '10px 12px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '500',
            fontSize: '14px',
            marginBottom: '12px',
            transition: 'all 0.2s'
          }} 
          onClick={() => setIsScanModalOpen(true)}
        >
          <FileText size={18} /> Resmi Dilekçe Oluştur
        </button>

        {/* Gelen E-postalar Button */}
        <button 
          className="nav-item" 
          style={{ 
            width: '100%', 
            border: '1px solid var(--border-color)', 
            background: !isChatMode && activeTab === 'emails' ? 'rgba(2, 132, 199, 0.1)' : 'transparent',
            color: !isChatMode && activeTab === 'emails' ? 'var(--text-primary)' : 'var(--text-secondary)',
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            padding: '10px 12px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '500',
            fontSize: '14px',
            marginBottom: '32px',
            transition: 'all 0.2s',
            position: 'relative'
          }} 
          onClick={() => { setIsChatMode(false); setActiveTab('emails'); }}
        >
          <Inbox size={18} /> Gelen E-postalar
          {zimbraStats.unread > 0 && zimbraLoggedIn && (
            <span style={{
              position: 'absolute', right: '10px', background: '#ef4444',
              color: '#fff', fontSize: '10px', fontWeight: '700',
              padding: '2px 6px', borderRadius: '10px', minWidth: '18px',
              textAlign: 'center'
            }}>{zimbraStats.unread}</span>
          )}
        </button>

        <div style={{ marginTop: 'auto' }}>
          <button 
            className="btn-secondary" 
            onClick={() => setIsDarkMode(!isDarkMode)} 
            style={{ 
              width: '100%', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              gap: '8px',
              padding: '10px',
              fontSize: '13px',
              borderColor: 'var(--border-color)',
              color: 'var(--text-secondary)'
            }}
          >
            {isDarkMode ? <Sun size={14} /> : <Moon size={14} />}
            {isDarkMode ? 'Açık Tema' : 'Koyu Tema'}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {!isChatMode ? (
          activeTab === 'dashboard' ? (
          <>
            <div className="content-wrapper" style={{ paddingTop: '48px' }}>
              <div className="page-header">
                <div>
                  <h2>Dilekçe İşlemleri</h2>
                  <p>Akademik Öğrenci Rehberi aracılığıyla resmi dilekçelerinizi oluşturun ve yönetin.</p>
                </div>
              </div>

              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-title">TOPLAM DILEKÇE</div>
                  <div className="stat-value white">{stats.total}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-title">DIŞA AKTARILMAYA HAZIR</div>
                  <div className="stat-value cyan">{stats.ready}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-title">İNCELEMEDE</div>
                  <div className="stat-value purple">{stats.review}</div>
                </div>
              </div>

              {/* Announcements Section */}
              <div className="cards-grid" style={{ marginBottom: '32px' }}>
                <div className="dashboard-card" style={{ gridColumn: '1 / -1', padding: '0', overflow: 'hidden' }}>
                  <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Bell size={18} style={{ color: 'var(--accent-blue)' }} />
                    <h3 style={{ fontSize: '16px', fontWeight: '600', margin: 0 }}>İSTE'den Güncel Duyurular</h3>
                  </div>
                  <div style={{ padding: '0' }}>
                    {announcements.length > 0 ? (
                      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                        {announcements.map((item, idx) => (
                          <li key={idx} style={{ borderBottom: idx !== announcements.length - 1 ? '1px solid var(--border-color)' : 'none' }}>
                            <a 
                              href={item.href} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              style={{ display: 'block', padding: '16px 24px', textDecoration: 'none', color: 'var(--text-primary)', transition: 'background 0.2s' }}
                              onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-sidebar)'}
                              onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
                                <div style={{ fontSize: '14px', fontWeight: '500', lineHeight: '1.4' }}>{item.title}</div>
                                {item.date && <div style={{ fontSize: '12px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{item.date}</div>}
                              </div>
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div style={{ padding: '24px', color: 'var(--text-secondary)', fontSize: '14px', textAlign: 'center' }}>
                        Duyurular yükleniyor veya bulunamadı...
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="cards-grid">
                {drafts.slice(0, 2).map((draft, idx) => (
                  <div key={draft.id} className="dashboard-card" onClick={() => handleStartChat(`${draft.title} hakkında bilgi ver.`)}>
                    <div className="card-header">
                      {draft.status === 'ready' && <span className="tag ready"><CheckCircle2 size={12} /> Dışa Aktarıma Hazır</span>}
                      {draft.status === 'drafting' && <span className="tag drafting"><FileText size={12} /> Taslak Aşamasında</span>}
                      {draft.status === 'review' && <span className="tag" style={{background: 'rgba(2,132,199,0.1)', color: 'var(--accent-purple)'}}><AlertTriangle size={12} /> İncelemede</span>}
                      {draft.status === 'finalized' && <span className="tag" style={{background: 'rgba(0,229,255,0.1)', color: 'var(--accent-blue)'}}><CheckCircle2 size={12} /> Onaylandı</span>}
                      <span style={{ fontSize: 12, color: '#94A3B8' }}>{new Date(draft.updated_at).toLocaleDateString('tr-TR')}</span>
                    </div>
                    <div className="card-title" style={{ fontSize: idx === 0 ? 22 : 18 }}>{draft.title}</div>
                    <div className="card-desc" style={{ fontSize: idx === 0 ? 14 : 13 }}>{draft.description}</div>
                    
                    {idx === 0 ? (
                      <div className="card-actions">
                        <button className="btn-primary" onClick={(e) => { e.stopPropagation(); setIsScanModalOpen(true); }}>Dilekçeyi Düzenle ve PDF İndir</button>
                        <button className="btn-secondary" onClick={(e) => { e.stopPropagation(); handleStartChat(`${draft.title} düzenlemek istiyorum.`); }}>Dilekçeyi Düzenle</button>
                      </div>
                    ) : (
                      <div className="progress-bar-container">
                        <div className="progress-track">
                          <div className="progress-fill" style={{ width: `${draft.progress}%` }}></div>
                        </div>
                        <div className="progress-text">{draft.progress}% Tamamlandı</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="cards-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                {drafts.slice(2, 5).map((draft, idx) => {
                  let icon = <FileText size={20} />;
                  let bgColors = { bg: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)', border: 'var(--border-color)' };
                  
                  if (draft.status === 'finalized') {
                    icon = <CheckCircle2 size={20} />;
                    bgColors = { bg: 'rgba(0,229,255,0.1)', color: 'var(--accent-blue)', border: 'rgba(0,229,255,0.2)' };
                  } else if (draft.status === 'review') {
                    icon = <AlertTriangle size={20} />;
                    bgColors = { bg: 'rgba(2,132,199,0.1)', color: 'var(--accent-purple)', border: 'rgba(2,132,199,0.2)' };
                  }
                  
                  return (
                    <div key={draft.id} className="dashboard-card" style={{ padding: '20px', borderColor: bgColors.border }} onClick={() => handleStartChat(`${draft.title} hakkında`)}>
                      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <div style={{ background: bgColors.bg, color: bgColors.color, padding: '10px', borderRadius: '8px' }}>
                          {icon}
                        </div>
                        <div>
                          <h4 style={{ fontSize: 14 }}>{draft.title}</h4>
                          <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            {draft.status === 'review' ? 'İnceleme Bekliyor' : new Date(draft.updated_at).toLocaleDateString('tr-TR')}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

            </div>
          </>
          ) : activeTab === 'directory' ? (
             <div className="content-wrapper" style={{ paddingTop: '48px' }}>
                <div className="page-header">
                  <div>
                    <h2>Akademik Kadro Rehberi</h2>
                    <p>İSTE Akademik ve İdari Personel iletişim bilgileri ({personnel.length} kişi)</p>
                  </div>
                </div>
                
                {/* Search & Filter Bar */}
                <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }}>
                  <div style={{ position: 'relative', flex: '1 1 300px' }}>
                    <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                    <input
                      type="text"
                      placeholder="İsim veya e-posta ara..."
                      value={dirSearch}
                      onChange={(e) => setDirSearch(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '12px 14px 12px 40px',
                        borderRadius: '10px',
                        border: '1px solid var(--border-color)',
                        background: 'var(--bg-sidebar)',
                        color: 'var(--text-primary)',
                        fontSize: '14px',
                        outline: 'none',
                        transition: 'border 0.2s'
                      }}
                    />
                  </div>
                  <select
                    value={dirDept}
                    onChange={(e) => setDirDept(e.target.value)}
                    style={{
                      padding: '12px 16px',
                      borderRadius: '10px',
                      border: '1px solid var(--border-color)',
                      background: 'var(--bg-sidebar)',
                      color: 'var(--text-primary)',
                      fontSize: '14px',
                      cursor: 'pointer',
                      minWidth: '200px'
                    }}
                  >
                    <option value="all">Tüm Bölümler</option>
                    {[...new Set(personnel.map(p => p.department).filter(Boolean))].sort().map(dept => (
                      <option key={dept} value={dept}>{dept}</option>
                    ))}
                  </select>
                </div>

                {/* Personnel Grid */}
                {(() => {
                  const filtered = personnel.filter(p => {
                    const matchSearch = !dirSearch || 
                      p.name.toLowerCase().includes(dirSearch.toLowerCase()) ||
                      (p.email && p.email.toLowerCase().includes(dirSearch.toLowerCase()));
                    const matchDept = dirDept === 'all' || p.department === dirDept;
                    return matchSearch && matchDept;
                  }).sort((a, b) => a.name.localeCompare(b.name, 'tr'));

                  const AVATAR_COLORS = [
                    '#0284c7', '#7c3aed', '#059669', '#d97706', '#dc2626',
                    '#2563eb', '#9333ea', '#0d9488', '#ca8a04', '#e11d48'
                  ];

                  const getInitials = (name) => {
                    const parts = name.split(' ').filter(Boolean);
                    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
                    return name.substring(0, 2).toUpperCase();
                  };

                  const getColor = (name) => {
                    let hash = 0;
                    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
                    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
                  };

                  return (
                    <>
                      <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                        {filtered.length} sonuç gösteriliyor
                      </div>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                        gap: '16px',
                        marginBottom: '40px'
                      }}>
                        {filtered.length > 0 ? filtered.map((p, idx) => (
                          <div key={idx} className="dashboard-card" style={{ 
                            padding: '20px', 
                            display: 'flex', 
                            gap: '16px', 
                            alignItems: 'flex-start',
                            transition: 'transform 0.2s, box-shadow 0.2s',
                            cursor: 'pointer'
                          }}
                          onClick={() => handlePersonClick(p)}
                          onMouseOver={(e) => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 12px 30px rgba(0,0,0,0.12)'; }}
                          onMouseOut={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = ''; }}
                          >
                            {/* Avatar */}
                            <div style={{
                              width: '48px',
                              height: '48px',
                              borderRadius: '12px',
                              background: `linear-gradient(135deg, ${getColor(p.name)}, ${getColor(p.name)}dd)`,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#fff',
                              fontWeight: '700',
                              fontSize: '16px',
                              flexShrink: 0,
                              letterSpacing: '1px'
                            }}>
                              {getInitials(p.name)}
                            </div>

                            {/* Info */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <h4 style={{ margin: '0 0 6px 0', fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {p.name}
                              </h4>
                              {p.department && (
                                <span style={{ 
                                  display: 'inline-block',
                                  background: 'rgba(2,132,199,0.08)', 
                                  color: 'var(--accent-blue)', 
                                  padding: '3px 8px', 
                                  borderRadius: '6px', 
                                  fontSize: '11px', 
                                  fontWeight: '600',
                                  marginBottom: '8px',
                                  letterSpacing: '0.3px'
                                }}>
                                  {p.department}
                                </span>
                              )}
                              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                                {p.email && (
                                  <a href={`mailto:${p.email}`} style={{ 
                                    display: 'flex', alignItems: 'center', gap: '4px',
                                    fontSize: '12px', color: 'var(--text-secondary)', 
                                    textDecoration: 'none', transition: 'color 0.2s'
                                  }}
                                  onMouseOver={(e) => e.currentTarget.style.color = 'var(--accent-blue)'}
                                  onMouseOut={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                                  >
                                    <Mail size={12} /> {p.email}
                                  </a>
                                )}
                                {p.profile_url && (
                                  <a href={p.profile_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{
                                    display: 'flex', alignItems: 'center', gap: '4px',
                                    fontSize: '12px', color: '#10b981', fontWeight: '600',
                                    textDecoration: 'none', transition: 'all 0.2s',
                                    background: 'rgba(16, 185, 129, 0.1)',
                                    padding: '4px 8px',
                                    borderRadius: '6px',
                                    border: 'none',
                                    cursor: 'pointer'
                                  }}
                                  onMouseOver={(e) => e.currentTarget.style.background = 'rgba(16, 185, 129, 0.2)'}
                                  onMouseOut={(e) => e.currentTarget.style.background = 'rgba(16, 185, 129, 0.1)'}
                                  >
                                    <ExternalLink size={12} /> Profil
                                  </a>
                                )}
                              </div>
                            </div>
                          </div>
                        )) : (
                          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)', gridColumn: '1 / -1' }}>
                            Sonuç bulunamadı.
                          </div>
                        )}
                      </div>
                    </>
                  );
                })()}
             </div>
          ) : activeTab === 'emails' ? (
          /* E-Posta Gelen Kutusu */
          <div className="content-wrapper" style={{ paddingTop: '48px' }}>
            <div className="page-header">
              <div>
                <h2>Gelen E-postalar</h2>
              </div>
              {zimbraLoggedIn && (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn-secondary" onClick={async () => {
                    setZimbraLoading(true);
                    try {
                      const res = await axios.post('http://localhost:8000/api/zimbra/inbox', { email: zimbraEmail });
                      setZimbraEmails(res.data.emails);
                      setZimbraStats(res.data.stats);
                    } catch(e) { setZimbraError('E-postalar yüklenemedi.'); }
                    setZimbraLoading(false);
                  }} style={{ padding: '8px 16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Loader2 size={14} className={zimbraLoading ? 'spinning' : ''} /> Yenile
                  </button>
                  <button className="btn-secondary" onClick={async () => {
                    try { await axios.post('http://localhost:8000/api/zimbra/logout', { email: zimbraEmail, password: '' }); } catch(e) {}
                    setZimbraLoggedIn(false); setZimbraEmails([]); setZimbraStats({ total: 0, academic: 0, announcement: 0, unread: 0 });
                  }} style={{ padding: '8px 16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#ef4444' }}>
                    <LogOut size={14} /> Çıkış
                  </button>
                </div>
              )}
            </div>

            {!zimbraLoggedIn ? (
              /* Login Form */
              <div style={{ maxWidth: '420px', margin: '60px auto' }}>
                <div className="dashboard-card" style={{ padding: '32px' }}>
                  <div style={{ textAlign: 'center', marginBottom: '28px' }}>
                    <div style={{ width: '56px', height: '56px', borderRadius: '16px', background: 'linear-gradient(135deg, #0284c7, #7c3aed)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                      <Lock size={24} color="#fff" />
                    </div>
                    <h3 style={{ margin: '0 0 6px', fontSize: '18px', color: 'var(--text-primary)' }}>Zimbra E-Posta Girişi</h3>
                    <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)' }}>İSTE e-posta hesabınızla giriş yapın</p>
                  </div>

                  {zimbraError && (
                    <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '13px', color: '#ef4444' }}>
                      {zimbraError}
                    </div>
                  )}

                  <form onSubmit={async (e) => {
                    e.preventDefault();
                    setZimbraLoading(true); setZimbraError('');
                    try {
                      await axios.post('http://localhost:8000/api/zimbra/login', { email: zimbraEmail, password: zimbraPassword });
                      localStorage.setItem('zimbraEmail', zimbraEmail);
                      setZimbraLoggedIn(true);
                      const res = await axios.post('http://localhost:8000/api/zimbra/inbox', { email: zimbraEmail });
                      setZimbraEmails(res.data.emails);
                      setZimbraStats(res.data.stats);
                    } catch(err) {
                      setZimbraError(err.response?.data?.detail || 'Giriş başarısız. E-posta veya şifrenizi kontrol edin.');
                    }
                    setZimbraLoading(false);
                  }}>
                    <div style={{ marginBottom: '14px' }}>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>E-posta Adresi</label>
                      <div style={{ position: 'relative' }}>
                        <Mail size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input type="email" placeholder="ornek@iste.edu.tr" value={zimbraEmail} onChange={(e) => setZimbraEmail(e.target.value)} required
                          style={{ width: '100%', padding: '11px 14px 11px 38px', borderRadius: '10px', border: '1px solid var(--border-color)', background: 'var(--bg-sidebar)', color: 'var(--text-primary)', fontSize: '14px', outline: 'none', boxSizing: 'border-box' }} />
                      </div>
                    </div>
                    <div style={{ marginBottom: '20px' }}>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>Şifre</label>
                      <div style={{ position: 'relative' }}>
                        <Lock size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input type={showPassword ? 'text' : 'password'} placeholder="••••••••" value={zimbraPassword} onChange={(e) => setZimbraPassword(e.target.value)} required
                          style={{ width: '100%', padding: '11px 42px 11px 38px', borderRadius: '10px', border: '1px solid var(--border-color)', background: 'var(--bg-sidebar)', color: 'var(--text-primary)', fontSize: '14px', outline: 'none', boxSizing: 'border-box' }} />
                        <button type="button" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}>
                          {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>
                    <button type="submit" className="new-chat-btn" disabled={zimbraLoading}
                      style={{ width: '100%', justifyContent: 'center', opacity: zimbraLoading ? 0.7 : 1 }}>
                      {zimbraLoading ? <><Loader2 size={16} className="spinning" /> Giriş Yapılıyor...</> : <><Inbox size={16} /> Giriş Yap</>}
                    </button>
                  </form>
                </div>
              </div>
            ) : (
              /* E-Posta Listesi */
              <>
                {/* Filtre Tabları */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
                  {[
                    { key: 'all', label: 'Tümü', count: zimbraStats.total, icon: <Inbox size={14} /> },
                    { key: 'academic', label: 'Hocalardan', count: zimbraStats.academic, icon: <GraduationCap size={14} />, color: '#10b981' },
                    { key: 'announcement', label: 'Duyurular', count: zimbraStats.announcement, icon: <Megaphone size={14} />, color: '#f59e0b' }
                  ].map(tab => (
                    <button key={tab.key} onClick={() => setEmailFilter(tab.key)} style={{
                      padding: '8px 16px', borderRadius: '10px', fontSize: '13px', fontWeight: '600',
                      border: emailFilter === tab.key ? '2px solid ' + (tab.color || 'var(--accent-blue)') : '1px solid var(--border-color)',
                      background: emailFilter === tab.key ? (tab.color || 'var(--accent-blue)') + '18' : 'transparent',
                      color: emailFilter === tab.key ? (tab.color || 'var(--accent-blue)') : 'var(--text-secondary)',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', transition: 'all 0.2s'
                    }}>
                      {tab.icon} {tab.label} <span style={{ opacity: 0.7 }}>({tab.count})</span>
                    </button>
                  ))}
                </div>

                {zimbraLoading ? (
                  <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-secondary)' }}>
                    <Loader2 size={32} className="spinning" style={{ marginBottom: '12px' }} />
                    <p>E-postalar yükleniyor...</p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {zimbraEmails.filter(e => emailFilter === 'all' || e.category === emailFilter).map((email, idx) => (
                      <div key={email.id || idx} className="dashboard-card" style={{
                        padding: '16px 20px', display: 'flex', gap: '14px', alignItems: 'flex-start',
                        cursor: 'pointer', transition: 'transform 0.15s, box-shadow 0.15s',
                        borderLeft: email.category === 'academic' ? '3px solid #10b981' : email.category === 'announcement' ? '3px solid #f59e0b' : '3px solid var(--border-color)',
                        opacity: email.is_read ? 0.75 : 1
                      }}
                      onClick={async () => {
                        setEmailDetailLoading(true);
                        setSelectedEmail(email); // temporary set for UI feedback
                        try {
                          const res = await axios.post('http://localhost:8000/api/zimbra/message', { email: zimbraEmail, msg_id: email.id });
                          setSelectedEmail({...email, ...res.data});
                        } catch (err) {
                          console.error("Failed to load message", err);
                          // Still show partial email if fails
                        }
                        setEmailDetailLoading(false);
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.transform = 'translateX(4px)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,0,0,0.08)'; }}
                      onMouseOut={(e) => { e.currentTarget.style.transform = 'translateX(0)'; e.currentTarget.style.boxShadow = ''; }}
                      >
                        <div style={{
                          width: '40px', height: '40px', borderRadius: '10px', flexShrink: 0,
                          background: email.category === 'academic' ? 'rgba(16,185,129,0.12)' : email.category === 'announcement' ? 'rgba(245,158,11,0.12)' : 'rgba(2,132,199,0.1)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                          {email.category === 'academic' ? <GraduationCap size={18} color="#10b981" /> : email.category === 'announcement' ? <Megaphone size={18} color="#f59e0b" /> : <Mail size={18} color="var(--accent-blue)" />}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                            <span style={{ fontSize: '13px', fontWeight: email.is_read ? '500' : '700', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>
                              {email.from_name || email.from_address}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', flexShrink: 0, marginLeft: '8px' }}>{email.date}</span>
                          </div>
                          <div style={{ fontSize: '14px', fontWeight: email.is_read ? '400' : '600', color: 'var(--text-primary)', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {!email.is_read && <span style={{ display: 'inline-block', width: '7px', height: '7px', borderRadius: '50%', background: '#0284c7', marginRight: '6px' }}></span>}
                            {email.subject}
                          </div>
                          {email.snippet && (
                            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{email.snippet}</p>
                          )}
                        </div>
                      </div>
                    ))}
                    {zimbraEmails.filter(e => emailFilter === 'all' || e.category === emailFilter).length === 0 && (
                      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
                        Bu kategoride e-posta bulunamadı.
                      </div>
                    )}
                  </div>
                )}

                {/* Email Reader Modal */}
                {selectedEmail && (
                  <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex',
                    alignItems: 'center', justifyContent: 'center', padding: '20px'
                  }}>
                    <div className="dashboard-card" style={{
                      width: '100%', maxWidth: '800px', maxHeight: '90vh',
                      background: 'var(--bg-card)', display: 'flex', flexDirection: 'column',
                      overflow: 'hidden', boxShadow: '0 24px 60px rgba(0,0,0,0.4)',
                      border: '1px solid var(--border-color)', borderRadius: '16px'
                    }}>
                      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', color: 'var(--text-primary)' }}>{selectedEmail.subject}</h3>
                          <div style={{ display: 'flex', gap: '16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                            <span style={{ fontWeight: '600' }}>Gönderen: {selectedEmail.from_name || selectedEmail.from_address}</span>
                            <span>Tarih: {selectedEmail.date}</span>
                          </div>
                        </div>
                        <button onClick={() => setSelectedEmail(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', transition: 'background 0.2s' }}
                          onMouseOver={e => e.currentTarget.style.background = 'rgba(0,0,0,0.05)'}
                          onMouseOut={e => e.currentTarget.style.background = 'transparent'}
                        ><X size={24} /></button>
                      </div>
                      
                      <div style={{ padding: '24px', overflowY: 'auto', flex: 1, background: 'var(--bg-main)' }}>
                        {emailDetailLoading ? (
                          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-secondary)' }}>
                            <Loader2 className="spinning" size={32} />
                          </div>
                        ) : (
                          <div 
                            className="email-reader-content"
                            style={{ padding: '0 8px' }}
                            dangerouslySetInnerHTML={{ __html: selectedEmail.body || '<i>İçerik bulunamadı veya yüklenemedi.</i>' }}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        ) : null
        ) : (
          /* Chat Interface */
          <div className="chat-container">
            <div className="messages-list">
              {messages.length === 0 && (
                <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '40px' }}>
                  <img src="/iste_logo.png" alt="İSTE Logo" style={{ width: '48px', height: '48px', opacity: 0.8, marginBottom: '16px' }} />
                  <h2>Size nasıl yardımcı olabilirim?</h2>
                  <p>Mevzuat ve başvuru süreçleri hakkında bilgi alabilirsiniz.</p>
                </div>
              )}
              {messages.map((msg, idx) => {
                // Check if message has the dynamic original file download tag
                const downloadMatch = msg.role === 'assistant' && msg.content && msg.content.match(/\[DOWNLOAD_FILE:(.*?)\]/);
                const fileToDownload = downloadMatch ? downloadMatch[1].trim() : null;
                
                // Remove the special tag so it stays completely hidden in the Markdown render
                const cleanContent = fileToDownload 
                  ? msg.content.replace(/\[DOWNLOAD_FILE:.*?\]/g, '').trim() 
                  : msg.content;
                
                return (
                  <div key={idx} className={`message ${msg.role}`}>
                    <div className="message-avatar">
                      {msg.role === 'user' ? <User size={18} /> : <img src="/iste_logo.png" alt="Portal" style={{ width: '24px', height: '24px', objectFit: 'contain' }} />}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0 }}>
                      <div className="message-content">
                        <ReactMarkdown>{cleanContent}</ReactMarkdown>
                      </div>
                      
                      {(() => {
                        const uniqueSources = [];
                        if (msg.sources && msg.sources.length > 0) {
                          const seen = new Set();
                          msg.sources.forEach(s => {
                            if (!s.source) return;
                            const parts = s.source.split(/[/\\]/);
                            const fname = parts[parts.length - 1];
                            const key = `${fname}-${s.page}`;
                            if(!seen.has(key)) {
                              seen.add(key);
                              uniqueSources.push({ ...s, cleanName: fname });
                            }
                          });
                        }
                        
                        if (uniqueSources.length === 0) return null;
                        
                        return (
                          <div className="sources-insights">
                            <div className="sources-insights-title">
                              <Library size={12} /> Kaynaklar:
                            </div>
                            <div className="sources-chips-scroll">
                              {uniqueSources.map((src, srcIdx) => {
                                const snippetId = `msg_${idx}_src_${srcIdx}`;
                                const isActive = activeSnippetId === snippetId;
                                return (
                                  <div 
                                    key={srcIdx} 
                                    className={`source-chip ${isActive ? 'active' : ''}`}
                                    onClick={() => setActiveSnippetId(isActive ? null : snippetId)}
                                  >
                                    <FileText size={14} />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }} title={src.cleanName}>{src.cleanName}</span>
                                    {src.page && src.page !== '?' && <span>(S. {src.page})</span>}
                                  </div>
                                );
                              })}
                            </div>
                            
                            {/* Show Snippet if active */}
                            {uniqueSources.map((src, srcIdx) => {
                              const snippetId = `msg_${idx}_src_${srcIdx}`;
                              if (activeSnippetId === snippetId) {
                                return (
                                  <div key={`snippet_${srcIdx}`} className="source-snippet-card">
                                    <div className="source-snippet-header">
                                      <span><strong>{src.cleanName}</strong> {src.page !== '?' ? `(Sayfa ${src.page}) ` : ''}içerisinden kesit:</span>
                                      <button 
                                        onClick={() => setActiveSnippetId(null)}
                                        style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex' }}
                                      >
                                        <X size={14} />
                                      </button>
                                    </div>
                                    <div style={{ fontStyle: 'italic' }}>
                                      "...<span className="highlight-text">{src.content.trim()}</span>..."
                                    </div>
                                    <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
                                      <button 
                                        onClick={() => handleDownloadSourceFile(src.cleanName)}
                                        className="tag ready"
                                        style={{ border: 'none', cursor: 'pointer', background: 'rgba(0, 229, 255, 0.1)', display: 'flex', gap: '6px', fontSize: '11px', padding: '6px 12px' }}
                                      >
                                        <Upload size={12} style={{ transform: 'rotate(180deg)' }} /> Belgeyi İndir
                                      </button>
                                    </div>
                                  </div>
                                );
                              }
                              return null;
                            })}
                          </div>
                        );
                      })()}
                      {fileToDownload && (
                        <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-start' }}>
                          <button 
                            className="btn-primary" 
                            style={{ 
                              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 
                              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.25)',
                              color: '#ffffff',
                              fontWeight: '600',
                              fontSize: '13px',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px',
                              padding: '10px 18px',
                              borderRadius: '8px',
                              border: 'none',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease'
                            }}
                            onClick={() => handleDownloadSourceFile(fileToDownload)}
                          >
                            <FileCheck size={16} /> Orijinal Boş Şablonu İndir ({fileToDownload})
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {isLoading && (
                <div className="message assistant">
                  <div className="message-avatar"><img src="/iste_logo.png" alt="Portal" style={{ width: '24px', height: '24px', objectFit: 'contain' }} /></div>
                  <div className="message-content">
                    <div className="typing-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-wrapper">
              <textarea 
                placeholder="Öğrenci rehberine sor..." 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                disabled={isLoading}
                rows={1}
                style={{ 
                  resize: 'none', 
                  minHeight: '22px', 
                  maxHeight: '120px', 
                  overflowY: 'auto'
                }}
                onInput={(e) => {
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                }}
              />
              <button className="send-btn" onClick={handleSendMessage} disabled={isLoading || !input.trim()}>
                <Send size={16} />
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Futuristic Auto-dilekçe Modal */}
      {isScanModalOpen && (
        <div className="scan-modal-overlay">
          <div className="scan-modal-card">
            <div className="scan-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div className="glow-icon-container">
                  <FileText size={18} />
                </div>
                <div>
                  <h3>Resmi Dilekçe Oluşturucu</h3>
                  <p className="scan-modal-subtitle">Bilgilerinizi doldurarak İSTE standartlarına uygun resmi A4 dilekçenizi saniyeler içinde hazırlayın.</p>
                </div>
              </div>
              <button className="close-modal-btn" onClick={() => { setIsScanModalOpen(false); setIsEdited(false); }}>
                <X size={18} />
              </button>
            </div>

            <div className="scan-modal-body">
              <div className="form-preview-grid">
                {/* Left Column: Form Fields */}
                <div className="form-column">
                  <div className="section-title">
                    <span>1</span> Öğrenci ve Bölüm Bilgileri
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Öğrenci Adı Soyadı</label>
                      <input type="text" value={fullname} onChange={(e) => setFullname(e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Öğrenci Numarası</label>
                      <input type="text" value={studentId} onChange={(e) => setStudentId(e.target.value)} />
                    </div>
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Bölüm / Program</label>
                      <input type="text" value={department} onChange={(e) => setDepartment(e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Telefon Numarası</label>
                      <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} />
                    </div>
                  </div>

                  <div className="section-title" style={{ marginTop: '16px' }}>
                    <span>2</span> Ders ve Sınav Bilgileri
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Ders Kodu</label>
                      <input type="text" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Ders Adı</label>
                      <input type="text" value={courseName} onChange={(e) => setCourseName(e.target.value)} />
                    </div>
                  </div>

                  <div className="section-title" style={{ marginTop: '16px' }}>
                    <span>3</span> Mazeret ve Rapor Bilgileri
                  </div>
                  <div className="form-group">
                    <label>Belgeyi Veren Kurum (Hastane vb.)</label>
                    <input type="text" value={institution} onChange={(e) => setInstitution(e.target.value)} />
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Mazeret Gerekçesi (Tanı)</label>
                      <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Mazeret Tarih Aralığı</label>
                      <input type="text" value={dateRange} onChange={(e) => setDateRange(e.target.value)} />
                    </div>
                  </div>

                  <div className="section-title" style={{ marginTop: '16px' }}>
                    <span>4</span> Dilekçe Metni Düzenle
                  </div>
                  <div className="form-group">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <label style={{ margin: 0 }}>Dilekçe İçeriği</label>
                      {isEdited && (
                        <button 
                          style={{ background: 'transparent', border: 'none', color: 'var(--accent-blue)', fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                          onClick={() => setIsEdited(false)}
                        >
                          <History size={11} /> Yazıyı Şablona Sıfırla
                        </button>
                      )}
                    </div>
                    <textarea 
                      className="petition-textarea" 
                      value={petitionText} 
                      onChange={(e) => {
                        setPetitionText(e.target.value);
                        setIsEdited(true);
                      }} 
                      rows={6}
                    />
                  </div>
                </div>

                {/* Right Column: Beautiful Live Paper Mockup Preview */}
                <div className="preview-column">
                  <div className="paper-header">RESMİ A4 KAĞIT ÖNİZLEME</div>
                  <div className="paper-sheet">
                    <div className="paper-university">İSKENDERUN TEKNİK ÜNİVERSİTESİ</div>
                    <div className="paper-dept">{department ? department.toUpperCase() : "..."} DEKANLIĞINA / MÜDÜRLÜĞÜNE</div>
                    <div className="paper-city">İskenderun</div>
                    
                    <div className="paper-date">Tarih: {new Date().toLocaleDateString('tr-TR')}</div>
                    
                    <div className="paper-info-block">
                      <div><strong>Adı Soyadı:</strong> {fullname}</div>
                      <div><strong>Öğrenci No:</strong> {studentId}</div>
                      <div><strong>Bölümü:</strong> {department}</div>
                      <div><strong>Telefon:</strong> {phone}</div>
                    </div>

                    <div className="paper-subject"><strong>KONU:</strong> Mazeret Sınavı Talebi ({courseCode} - {courseName})</div>

                    <div className="paper-body">
                      {petitionText || "Dilekçe içeriği burada görüntülenecektir..."}
                    </div>

                    <div className="paper-signature-block">
                      <div>İmza</div>
                      <div style={{ marginTop: '8px', fontWeight: '500' }}>{fullname}</div>
                    </div>

                    <div className="paper-attachments">
                      <strong>EKLER:</strong>
                      <div>1. Mazeret Belgesi / Rapor Fotokopisi ({institution || "..."} onaylı, {dateRange || "..."} tarihli)</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="scan-modal-footer">
              <button className="btn-secondary" onClick={() => { setIsScanModalOpen(false); setIsEdited(false); }}>
                Kapat
              </button>
              <button className="btn-primary download-action-btn" onClick={handleSaveAndDownloadPDF}>
                <Check size={16} /> Dilekçeyi Kaydet ve PDF İndir
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Profile Modal */}
      {isProfileModalOpen && selectedPerson && (
        <div className="scan-modal-overlay" onClick={() => setIsProfileModalOpen(false)}>
          <style>{`
            @keyframes profileScaleFade {
              0% { opacity: 0; transform: scale(0.9) translateY(20px); }
              100% { opacity: 1; transform: scale(1) translateY(0); }
            }
          `}</style>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ 
            maxWidth: '480px', 
            width: '90%', 
            padding: '0', 
            background: 'var(--bg-card)', 
            borderRadius: '20px', 
            overflow: 'hidden', 
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            border: '1px solid var(--border-color)',
            animation: 'profileScaleFade 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards'
          }}>
            {/* Header / Avatar Area */}
            <div style={{ 
              background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%)',
              padding: '40px 24px 24px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              position: 'relative'
            }}>
              <button 
                onClick={() => setIsProfileModalOpen(false)}
                style={{ position: 'absolute', top: '16px', right: '16px', background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '8px', borderRadius: '50%', transition: 'background 0.2s' }}
                onMouseOver={e => e.currentTarget.style.background = 'rgba(0,0,0,0.05)'}
                onMouseOut={e => e.currentTarget.style.background = 'transparent'}
              >
                <X size={20} />
              </button>
              
              <div style={{
                width: '100px', height: '100px', borderRadius: '50%',
                background: 'linear-gradient(135deg, #0284c7, #0369a1)',
                color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '32px', fontWeight: '700', letterSpacing: '1px',
                boxShadow: '0 10px 25px rgba(2, 132, 199, 0.3)',
                marginBottom: '16px', border: '4px solid var(--bg-card)'
              }}>
                {selectedPerson.name.split(' ').filter(Boolean).length >= 2 
                  ? (selectedPerson.name.split(' ')[0][0] + selectedPerson.name.split(' ')[selectedPerson.name.split(' ').length - 1][0]).toUpperCase()
                  : selectedPerson.name.substring(0, 2).toUpperCase()}
              </div>
              
              <h2 style={{ margin: '0 0 8px 0', fontSize: '22px', fontWeight: '700', color: 'var(--text-primary)', textAlign: 'center' }}>
                {selectedPerson.name}
              </h2>
              
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                {personDetailLoading ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                    <Loader2 size={16} className="spinning" /> Yükleniyor...
                  </div>
                ) : personDetail?.title ? (
                  <span style={{ fontSize: '15px', color: 'var(--text-secondary)', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {personDetail.title}
                  </span>
                ) : (
                  <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Öğretim Elemanı</span>
                )}
                
                {selectedPerson.department && (
                  <span style={{ background: 'var(--bg-sidebar)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: '500' }}>
                    {selectedPerson.department}
                  </span>
                )}
              </div>
            </div>

            {/* Content Area */}
            <div style={{ padding: '24px' }}>
              {/* Badges / Links */}
              {personDetail && !personDetailLoading && (
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginBottom: '24px' }}>
                  {personDetail.yoksis && (
                    <a href={personDetail.yoksis} target="_blank" rel="noopener noreferrer" style={{
                      background: '#ef4444', color: 'white', padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '700', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 4px 12px rgba(239, 68, 68, 0.25)', transition: 'transform 0.2s'
                    }} onMouseOver={e => e.currentTarget.style.transform='translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform='translateY(0)'}>
                      YÖKSİS
                    </a>
                  )}
                  {personDetail.orcid && (
                    <a href={personDetail.orcid} target="_blank" rel="noopener noreferrer" style={{
                      background: '#64748b', color: 'white', padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '700', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 4px 12px rgba(100, 116, 139, 0.25)', transition: 'transform 0.2s'
                    }} onMouseOver={e => e.currentTarget.style.transform='translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform='translateY(0)'}>
                      ORCID
                    </a>
                  )}
                </div>
              )}

              {/* Contact */}
              <div style={{ background: 'var(--bg-sidebar)', padding: '16px', borderRadius: '12px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ background: 'rgba(2, 132, 199, 0.1)', padding: '10px', borderRadius: '50%', color: 'var(--accent-blue)' }}>
                  <Mail size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '2px' }}>E-Posta Adresi</div>
                  <a href={`mailto:${selectedPerson.email}`} style={{ color: 'var(--text-primary)', fontWeight: '500', textDecoration: 'none', fontSize: '14px' }}>{selectedPerson.email}</a>
                </div>
              </div>

              {/* Accordions */}
              {personDetail && !personDetailLoading && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {/* Direct Tasks (No Accordion, No Header) */}
                  {personDetail.tasks && personDetail.tasks.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', background: 'var(--bg-sidebar)', padding: '16px', borderRadius: '12px' }}>
                      {personDetail.tasks.map((t, i) => (
                        <div key={i} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                          <Info size={18} color="#ec4899" style={{ flexShrink: 0, marginTop: '2px' }} />
                          <div>
                            <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>{t.unit}</div>
                            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{t.duty}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Direct Office Hours (No Accordion) */}
                  {(() => {
                    const hours = personDetail.office_hours;
                    if (!hours || hours.length === 0) return null;

                    const firstName = selectedPerson.name.split(' ')[0];
                    const formattedName = firstName.charAt(0).toUpperCase() + firstName.slice(1).toLocaleLowerCase('tr-TR');
                    
                    const schedule = {};
                    let hasValidHours = false;
                    
                    hours.forEach(h => {
                      const match = h.time.match(/([^\(]+)\s*\(\s*([0-9:]+)\s*-\s*([0-9:]+)\s*\)/);
                      if (match) {
                        hasValidHours = true;
                        let day = match[1].trim().toLocaleLowerCase('tr-TR');
                        const start = match[2].trim();
                        const end = match[3].trim();
                        
                        if (!schedule[day]) schedule[day] = [];
                        schedule[day].push({start, end});
                      }
                    });

                    if (!hasValidHours) return null;

                    const sentences = [];
                    for (const [day, slots] of Object.entries(schedule)) {
                      slots.sort((a, b) => a.start.localeCompare(b.start));
                      const merged = [];
                      let current = slots[0];
                      for (let i = 1; i < slots.length; i++) {
                        if (current.end === slots[i].start) {
                          current.end = slots[i].end;
                        } else {
                          merged.push(current);
                          current = slots[i];
                        }
                      }
                      merged.push(current);
                      
                      const timeStrs = merged.map(m => `${m.start} ile ${m.end} saatleri arasında`);
                      const timeText = timeStrs.join(', ayrıca ');
                      sentences.push(`${day} günü ${timeText}`);
                    }

                    const daysText = sentences.join(' ve ');
                    const naturalSentence = `${formattedName} Hoca, ${daysText} ofisinde bulunmaktadır.`;

                    return (
                      <div style={{ 
                        marginTop: '8px', 
                        background: 'rgba(16, 185, 129, 0.08)', 
                        borderLeft: '4px solid #10b981',
                        padding: '16px', 
                        borderRadius: '0 8px 8px 0',
                        color: 'var(--text-primary)',
                        fontSize: '14px',
                        lineHeight: '1.6',
                        display: 'flex',
                        gap: '12px',
                        alignItems: 'flex-start'
                      }}>
                        <Clock size={20} color="#10b981" style={{ flexShrink: 0, marginTop: '2px' }} />
                        <div>{naturalSentence}</div>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
