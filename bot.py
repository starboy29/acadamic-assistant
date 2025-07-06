import discord
from discord import app_commands
from config import DISCORD_TOKEN, GUILD_ID
from mongo_handler import save_pdf, get_pdfs_by_metadata,add_assignment
from io import BytesIO
from datetime import datetime
from google_calendar import create_event

user_upload_context = {}

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)

        @self.tree.command(guild=guild, name="ping", description="Check if bot is alive")
        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message("🏓 Pong!")

        @self.tree.command(guild=guild, name="upload", description="Set subject/chapter/topic for next file")
        @app_commands.describe(
            subject="Subject name (e.g., Physics)",
            chapter="Chapter number/name",
            topic="Topic"
        )
        async def upload(interaction: discord.Interaction, subject: str, chapter: str, topic: str):
            user_upload_context[interaction.user.id] = {
                "subject": subject,
                "chapter": chapter,
                "topic": topic
            }
            await interaction.response.send_message(
                f"📥 Ready to upload file for **{subject} / {chapter} / {topic}**"
            )

        @self.tree.command(guild=guild, name="get_notes", description="Get saved notes by subject and chapter")
        @app_commands.describe(
            subject="Subject name (e.g., Physics)",
            chapter="Chapter number/name"
        )
        async def get_notes(interaction: discord.Interaction, subject: str, chapter: str):
            await interaction.response.defer(thinking=True)
            notes = get_pdfs_by_metadata(subject, chapter)

            if not notes:
                await interaction.followup.send("❌ No notes found for that subject and chapter.")
                return

            for filename, file_bytes in notes:
                await interaction.followup.send(
                    content=f"📄 **{filename}** from {subject} / {chapter}",
                    file=discord.File(fp=BytesIO(file_bytes), filename=filename)
                )
        @self.tree.command(guild=guild, name="set_assignment", description="Add a new assignment with deadline")
        @app_commands.describe(
            subject="Subject name",
            chapter="Chapter number or name",
            topic="Topic name",
            deadline="Deadline in ISO format (e.g., 2025-06-22T23:59:00)",
            description="Description of the assignment"
        )
        async def set_assignment(
            interaction: discord.Interaction,
            subject: str,
            chapter: str,
            topic: str,
            deadline: str,
            description: str
        ):
            # ✅ Defer immediately to avoid timeout
            await interaction.response.defer(ephemeral=True, thinking=True)

            # Validate date format
            try:
                datetime.fromisoformat(deadline)
            except ValueError:
                await interaction.followup.send("❌ Invalid deadline format. Use YYYY-MM-DDTHH:MM:SS", ephemeral=True)
                return

            # Save to MongoDB
            add_assignment(subject, chapter, topic, deadline, description)

            # Create calendar event
            try:
                event_link = create_event(subject, chapter, topic, deadline, description)
            except Exception as e:
                print(f"⚠️ Calendar error: {e}")
                event_link = None

            # Construct and send reply
            reply = f"✅ Assignment set for **{subject} - Chapter {chapter} - {topic}**"
            if event_link:
                reply += f"\n📅 [View in Calendar]({event_link})"

            await interaction.followup.send(reply, ephemeral=True)

    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.attachments:
            return

        user_id = message.author.id
        if user_id not in user_upload_context:
            await message.channel.send("❗ Please use `/upload` before sending a file.")
            return

        context = user_upload_context.pop(user_id)
        for attachment in message.attachments:
            file_bytes = await attachment.read()
            filename = attachment.filename

            # Save to MongoDB GridFS
            save_pdf(file_bytes, filename, context)

            await message.channel.send(
                f"✅ **{filename}** saved under:\n"
                f"> **Subject**: {context['subject']}\n"
                f"> **Chapter**: {context['chapter']}\n"
                f"> **Topic**: {context['topic']}"
            )

client = MyClient()

@client.event
async def on_ready():
    print(f"🤖 Bot online as {client.user}")

client.run(DISCORD_TOKEN)

