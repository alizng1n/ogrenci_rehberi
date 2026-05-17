import { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, History, Library, Settings, 
  Send, Search, Plus, CheckCircle2, AlertTriangle, 
  FileText, ArrowRight, User, Sun, Moon, Home,
  Upload, Camera, Check, X, FileCheck
} from 'lucide-react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './index.css';

function App() {
  const [isChatMode, setIsChatMode] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [stats, setStats] = useState({ total: 0, ready: 0, review: 0, efficiency: 0 });
  const [drafts, setDrafts] = useState([]);
  const [sources, setSources] = useState([]);
  const messagesEndRef = useRef(null);

  // Dilekçe Modal State
  const [isScanModalOpen, setIsScanModalOpen] = useState(false);

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
        const [statsRes, draftsRes, sourcesRes] = await Promise.all([
          axios.get('http://localhost:8000/api/stats'),
          axios.get('http://localhost:8000/api/drafts'),
          axios.get('http://localhost:8000/api/sources')
        ]);
        setStats(statsRes.data);
        setDrafts(draftsRes.data);
        setSources(sourcesRes.data);
      } catch (err) {
        console.error("Failed to fetch data", err);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.remove('light-theme');
    } else {
      document.body.classList.add('light-theme');
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
      setMessages([...newMessages, { 
        role: 'assistant', 
        content: "Üzgünüm, bir hata oluştu. Lütfen sunucu bağlantısını kontrol edin." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
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
            background: !isChatMode ? 'rgba(2, 132, 199, 0.1)' : 'transparent',
            color: !isChatMode ? 'var(--text-primary)' : 'var(--text-secondary)',
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
          onClick={() => setIsChatMode(false)}
        >
          <Home size={18} /> Menü (Ana Sayfa)
        </button>

        <button className="new-chat-btn" onClick={() => handleStartChat()} style={{ marginBottom: '32px' }}>
          <Plus size={18} />
          Yeni Sorgulama
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
          <>
            <div className="content-wrapper" style={{ paddingTop: '48px' }}>
              <div className="page-header">
                <div>
                  <h2>Dilekçe İşlemleri</h2>
                  <p>Akademik Öğrenci Rehberi aracılığıyla resmi dilekçelerinizi oluşturun ve yönetin.</p>
                </div>
                <button className="new-chat-btn" style={{ background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)', margin: 0, boxShadow: '0 4px 12px rgba(2, 132, 199, 0.3)' }} onClick={() => setIsScanModalOpen(true)}>
                  <FileText size={18} />
                  Resmi Dilekçe Oluştur
                </button>
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
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <div className="message-content">
                        <ReactMarkdown>{cleanContent}</ReactMarkdown>
                      </div>
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
              <input 
                type="text" 
                placeholder="Mevzuat sistemine sor..." 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                disabled={isLoading}
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
    </div>
  );
}

export default App;
