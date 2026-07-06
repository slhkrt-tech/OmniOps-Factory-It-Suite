"""Merge hand-written EN overrides for remaining Turkish PO entries."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "locale"
OVERRIDES = BASE / "en_manual_overrides.json"

REMAINING = {
    "CRİTİCAL UYARI: Ağ kurtarma başlatılıyor. Seçilen yedek cihazın hafızasına yazılacak. Onaylıyor musunuz?": (
        "CRITICAL WARNING: Network recovery is starting. The selected backup will be written to device memory. Do you confirm?"
    ),
    "Bağlanır": "Connects",
    "Üst:": "Parent:",
    "Türk Telekom": "Turk Telekom",
    "OmniOps Bilgi Bankası": "OmniOps Knowledge Base",
    "Ağ, yazıcı, şifre sıfırlama, VPN...": "Network, printer, password reset, VPN...",
    'Henüz kabinlere yerleştirilmiş bir cihaz bulunmuyor. Lütfen Envanter sayfasından cihaz ekleyip \\"Kabin Adı\\" ve \\"Başlangıç U\\" değerlerini girin.': (
        'No devices are placed in racks yet. Add devices from the Inventory page and set "Rack Name" and "Starting U" values.'
    ),
    "Ağ Adresi": "Network Address",
    "Kullanılabilir IP Aralığı": "Available IP Range",
    "Subnetting Nasıl Yapılır?": "How to Subnet?",
    "Bölmek istediğiniz ana ağ adresini ve her bir alt ağın sahip olmasını istediğiniz yeni prefix değerini sol panele girin. Sistem alt ağları otomatik olarak hesaplar.": (
        "Enter the main network address and desired new prefix in the left panel. The system calculates subnets automatically."
    ),
    "IP Aralığı Tespiti": "IP Range Detection",
    "Sistem Olayları ve Loglar - OmniOps": "System Events and Logs - OmniOps",
    "Sistem Olayları": "System Events",
    "Platform üzerinde gerçekleştirilen kritik işlemlerin geçmişini buradan inceleyebilirsiniz.": (
        "Review the history of critical operations performed on the platform here."
    ),
    "Tüm İşlemler": "All Operations",
    "Sistem İşlemi": "System Operation",
    "Kayıtlı sistem olayı bulunamadı.": "No system events recorded.",
    "Önceki": "Previous",
    "Talep Detayı": "Ticket Details",
    "Öncelik:": "Priority:",
    "Oluşturan:": "Created by:",
    "Henüz yorum yok.": "No comments yet.",
    "Durum Güncelle": "Update Status",
    "Güncelle": "Update",
    "— Seçin —": "— Select —",
    "Dosya Yükle": "Upload File",
    "OmniOps - Ağ Topolojisi": "OmniOps - Network Topology",
    "Dinamik Ağ Topolojisi": "Dynamic Network Topology",
    "Cihazlar arası hiyerarşik bağlantıları ve ağ haritasını interaktif olarak inceleyin.": (
        "Explore hierarchical device connections and the network map interactively."
    ),
    "Cihazları sürükleyebilir, tekerlek ile yakınlaşabilirsiniz.": "You can drag devices and zoom with the scroll wheel.",
    "Uç Cihazlar": "Edge Devices",
    "Kullanıcı Yönetimi - OmniOps": "User Management - OmniOps",
    "Yeni Kullanıcı": "New User",
    "Oluştur": "Create",
    "Kayıt": "Record",
    "Hızlı hizmet kataloğundan seçim yapabilir veya özel teknik sorunlarınızı bildirebilirsiniz.": (
        "Choose from the quick service catalog or report your own technical issues."
    ),
    "Hızlı Hizmet Kataloğu": "Quick Service Catalog",
    "Yönetici Onayı Gerektirir": "Requires Admin Approval",
    "Manuel Arıza Bildirimi": "Manual Incident Report",
    "Talep İletiliyor...": "Submitting request...",
    "Talep Geçmişiniz": "Your Ticket History",
    "İşlem Bekliyor": "Pending Action",
    "Henüz bir destek talebi oluşturmadınız.": "You have not created a support ticket yet.",
    "Çalışma Alanı Studio": "Workspace Studio",
    "Sektörünüze göre modülleri, etiketleri ve panel düzenini özelleştirin. Tekstil tesisindeki BT ekranı ile güneş santrali operasyonu aynı olmamalı.": (
        "Customize modules, labels, and panel layout for your industry. A textile plant IT screen should not look like a solar farm operation."
    ),
    "Aktif Modül": "Active Module",
    "Sürükle-Bırak": "Drag and Drop",
    "Sektör Şablonları": "Industry Templates",
    "modül": "module",
    "Kişisel Tercihler": "Personal Preferences",
    "Otomatik (sektöre göre)": "Automatic (by industry)",
    "Sürükle-bırak düzenleme": "Drag-and-drop layout",
    "Panel düzenini sıfırla": "Reset panel layout",
    "Kurum Profili (Yönetici)": "Organization Profile (Admin)",
    "Birincil sektör": "Primary industry",
    "Özel sektör adı": "Custom industry name",
    "Örn: Güneş Paneli Üretimi": "e.g. Solar Panel Manufacturing",
    "Alt başlık": "Subtitle",
    "Aktif modüller": "Active modules",
    "Sürükle-Bırak İpuçları": "Drag-and-Drop Tips",
    "Ana Panel'de widget başlıklarından tutup sıralamayı değiştirebilirsiniz.": (
        "On the main dashboard, drag widget headers to reorder them."
    ),
    "Satış Kanban kartlarını sütunlar arasında sürükleyin.": "Drag sales Kanban cards between columns.",
    "Portföy envanterinde satır sırasını sürükleyerek düzenleyin.": "Reorder rows in portfolio inventory by dragging.",
    "Düzen otomatik kaydedilir; sıfırlamak için yukarıdaki butonu kullanın.": (
        "Layout saves automatically; use the button above to reset."
    ),
    "Yeni Ticket Aç": "Open New Ticket",
    "Servis masası ve sistem biletleri": "Service desk and system tickets",
    "Departman kartelası, modüller ve doküman merkezi": "Department chart, modules, and document center",
    "QR/Barkod Tarayıcı": "QR/Barcode Scanner",
    "Etiket okut, varlığa anında git": "Scan a tag and jump to the asset instantly",
    "Odoo bağlantıları ve kamera health poll": "Odoo connections and camera health polling",
    "VPN, chat, kamera ve uygulama portalı": "VPN, chat, camera, and application portal",
    "Takvim, CMDB, denetim ve çıktılar": "Calendar, CMDB, audit, and exports",
    "Canlıya alma, readiness ve ilk kurulum kontrolleri": "Go-live, readiness, and initial setup checks",
    "Derin Ağ Keşfi": "Deep Network Discovery",
    "PDF ve CSV çıktıları": "PDF and CSV exports",
    "Yönetici Bilgilendirme": "Executive Briefing",
    "Tek sayfa özet, PDF ve Word çıktıları": "One-page summary, PDF and Word exports",
    "Yeni donanım envantere başarıyla eklendi.": "New hardware added to inventory successfully.",
    "Yazılım lisansı başarıyla kaydedildi.": "Software license saved successfully.",
    "Tedarikçi sözleşmesi başarıyla kaydedildi.": "Vendor contract saved successfully.",
    "🛡️ ITIL Kuralı: Sistem güvenliği gereği konfigürasyonlar doğrudan cihaza yazılamaz. Talebiniz 'Değişiklik Onay Havuzuna (CAB)' iletildi. Yetkili onayından sonra uygulanacaktır.": (
        "🛡️ ITIL rule: For security, configurations cannot be pushed directly to devices. Your request was sent to the Change Approval Board (CAB) and will run after approval."
    ),
    "SSH kullanıcı adı veya şifresi tanımlı değil. Cihaz profilinde SSH bilgilerini girin.": (
        "SSH username or password is not configured. Enter SSH credentials on the device profile."
    ),
    "✅ Disaster Recovery Başarılı: Eski konfigürasyon cihaza yazıldı ve ağ saniyeler içinde kurtarıldı!": (
        "✅ Disaster Recovery successful: Previous configuration was restored to the device and the network recovered within seconds!"
    ),
    "IP adresi başarıyla atandı ve kayıt edildi.": "IP address assigned and saved successfully.",
    "Uzak cihaz CPU/RAM metrikleri için SNMP veya ajan entegrasyonu gerekir.": (
        "SNMP or agent integration is required for remote device CPU/RAM metrics."
    ),
    "Port haritası bilgileri başarıyla güncellendi.": "Port map updated successfully.",
    "Yeni bilgi bankası makalesi başarıyla eklendi.": "New knowledge base article added successfully.",
    "Talep metni hassas veri içerdiği için DLP politikası tarafından engellendi.": (
        "The request was blocked by DLP policy because it contained sensitive data."
    ),
    "Destek talebiniz başarıyla alındı.": "Your support request was received successfully.",
    "Cihaz ve konfigürasyon alanı boş bırakılamaz.": "Device and configuration fields cannot be empty.",
    "SSH kullanıcı adı veya şifresi tanımlı değil.": "SSH username or password is not configured.",
    "Talep formu geçersiz.": "Ticket form is invalid.",
    "Kullanıcı formu geçersiz.": "User form is invalid.",
    "Bu dönemde açılmış bilet bulunmuyor.": "No tickets opened in this period.",
    "Bilgi işlem için tek çalışma alanı": "One workspace for IT operations",
    "Uygulandı": "Applied",
    "BT Varlık": "IT Asset",
    "Lisans": "License",
    "Fabrika Alanı": "Factory Area",
    "İş Uygulaması": "Business Application",
    "Rapor Şablonu": "Report Template",
    "Endpoint Cihazı": "Endpoint Device",
    "Yönetilen Doküman": "Managed Document",
    "ERP Bağlantısı": "ERP Connection",
    "Entegrasyon Merkezi": "Integration Center",
    "Kameralar": "Cameras",
    "Ağ Cihazları": "Network Devices",
    "Endpointler": "Endpoints",
    "Yazıcılar": "Printers",
    "İş Uygulamaları": "Business Applications",
    "Ticketlar": "Tickets",
    "Dokümanlar": "Documents",
    "Bakım İşleri": "Maintenance Jobs",
    "Sarf/Yedek": "Consumables / Spares",
    "IT Varlıkları": "IT Assets",
}


def main() -> None:
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    overrides.update(REMAINING)
    OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Overrides: {len(overrides)}")


if __name__ == "__main__":
    main()
