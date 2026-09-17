from django.contrib import admin

# Register your models here.
from .models import Bot, Conversation, Message

admin.site.register(Bot)
admin.site.register(Conversation)
admin.site.register(Message)