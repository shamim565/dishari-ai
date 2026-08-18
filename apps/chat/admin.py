from django.contrib import admin

from apps.chat.models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "role", "lang", "source", "journey", "content_preview")
    list_filter = ("role", "source", "lang")
    search_fields = ("content",)
    readonly_fields = ("created_at",)

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:80]
