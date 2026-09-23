from django.db import models

# Create your models here.
from django.contrib.auth.models import User

class Bot(models.Model):
    name=models.CharField(max_length=100)
    description=models.TextField(blank=True)
    is_active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Conversation(models.Model):
    bot=models.ForeignKey(Bot, on_delete=models.CASCADE)
    user=models.ForeignKey(User, on_delete=models.CASCADE)
    title=models.CharField(max_length=200, blank=True, default="")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        indexes=[
            models.Index(fields=['bot']),
            models.Index(fields=['updated_at'])
        ]

    @property
    def display_title(self):
        """
        Sidebar label: the saved title, else the first user
        message, else a placeholder for an empty chat.
        """
        if self.title:
            return self.title

        first = self.message_set.filter(
            sender="user"
        ).order_by("created_at").first()

        if first:
            return first.content[:40]

        return "New Chat"

    def __str__(self):
        return f"Conversation {self.id}"

class Message(models.Model):
    SENDER_CHOICES=[
        ('user', 'User'),
        ('assistant', 'Assistant')
    ]
    conversation=models.ForeignKey(Conversation, on_delete=models.CASCADE)
    sender=models.CharField(max_length=10, choices=SENDER_CHOICES)
    content=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes=[
            models.Index(fields=['conversation']),
            models.Index(fields=['created_at'])
        ]

    def __str__(self):
        return f"{self.sender}: {self.content[:50]}..."
