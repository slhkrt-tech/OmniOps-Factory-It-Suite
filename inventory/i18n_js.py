"""Shared JavaScript UI strings resolved server-side for i18n."""

from django.utils.translation import gettext


def get_omniops_i18n() -> dict[str, str]:
    return {
        'noResults': gettext('Sonuç bulunamadı. Farklı bir kelime deneyin.'),
        'searchServiceDown': gettext('Arama servisi şu an yanıt vermiyor.'),
        'processing': gettext('İşleniyor...'),
        'noNotifications': gettext('Bildirim yok.'),
        'heatmapNone': gettext('Yok'),
        'heatmapLow': gettext('Düşük'),
        'heatmapMedium': gettext('Orta'),
        'heatmapHigh': gettext('Yüksek'),
        'queueEmpty': gettext('Bekleyen kayıt yok.'),
        'syncWarning': gettext('Senkronizasyon uyarısı:'),
        'apiResponseFailed': gettext('API yanıtı başarısız'),
        'syncFailed': gettext('#%(id)s senkronize edilemedi'),
        'online': gettext('Online'),
        'offline': gettext('Offline'),
        'kanbanSaveFailed': gettext(
            'Kanban güncellemesi kaydedilemedi. Yetki veya oturum durumunu kontrol edin.'
        ),
        'kanbanNetworkError': gettext('Kanban güncellemesi sırasında ağ hatası oluştu.'),
        'recordNotFound': gettext('Kayıt bulunamadı: %(code)s'),
        'cameraStartFailed': gettext(
            'Kamera başlatılamadı. Manuel kod girişini kullanın.'
        ),
        'cameraAccessDenied': gettext('Kamera erişimi yok. Manuel kod girişini kullanın.'),
        'deleteUserConfirm': gettext('Kullanıcıyı silmek istediğinize emin misiniz?'),
        'changeApproved': gettext('Uygulandı'),
        'changePending': gettext('Onay Bekliyor'),
        'changeRejected': gettext('Reddedildi'),
        'slaViolation': gettext('SLA İHLALİ'),
        'slaRemaining': gettext('%(hours)s Saat, %(minutes)s Dk Kaldı'),
        'backupCriticalConfirm': gettext(
            'CRİTİCAL UYARI: Ağ kurtarma başlatılıyor. Seçilen yedek cihazın hafızasına yazılacak. Onaylıyor musunuz?'
        ),
    }
