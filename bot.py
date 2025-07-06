import discord
from discord import app_commands
from config import DISCORD_TOKEN, GUILD_ID
from mongo_handler import add_assignment,get_notes_by_subject_and_chapter
from io import BytesIO
from datetime import datetime
from google_calendar import create_event
from google_drive import upload_file_to_drive
from mongo_handler import store_file_metadata

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

        @self.tree.command(name="get_notes", description="View uploaded notes by subject and chapter")
        @app_commands.describe(
            subject="Subject name (e.g. Physics)",
            chapter="Chapter name/number (e.g. 2)"
        )
        async def get_notes(interaction: discord.Interaction, subject: str, chapter: str):
            await interaction.response.defer(ephemeral=True, thinking=True)

            files = get_notes_by_subject_and_chapter(subject, chapter)

            if not files:
                await interaction.followup.send("📂 No notes found for that subject and chapter.", ephemeral=True)
                return

            reply = f"📚 **Notes for {subject} / Chapter {chapter}:**\n\n"
            for f in files[:15]:
                reply += f"• **{f['filename']}** → [Open]({f['drive_link']})\n"

            if len(files) > 15:
                reply += f"\n...and {len(files) - 15} more."

            await interaction.followup.send(reply, ephemeral=True)

        @self.tree.command(guild=guild, name="set_assignment", description="Add a new assignment with deadline and optional file")
        @app_commands.describe(
            subject="Subject name",
            chapter="Chapter number or name",
            topic="Topic name",
            deadline="Deadline in YYYY-MM-DD format (e.g., 2025-06-22)",
            description="Description of the assignment",
            file="Upload a related file (PDF preferred)"
        )
        async def set_assignment(
            interaction: discord.Interaction,
            subject: str,
            chapter: str,
            topic: str,
            deadline: str,
            description: str,
            file: discord.Attachment = None
        ):
            # ✅ Defer immediately
            await interaction.response.defer(ephemeral=True, thinking=True)

            # ✅ Append time if only date is given
            try:
                deadline_iso = deadline + "T23:59:00"
                datetime.fromisoformat(deadline_iso)
            except ValueError:
                await interaction.followup.send("❌ Invalid deadline format. Use YYYY-MM-DD", ephemeral=True)
                return

            # ✅ Upload to Google Drive (if file provided)
            file_id = None
            drive_link = None

            if file:
                try:
                    file_bytes = await file.read()
                    filename = file.filename

                    file_id, drive_link = upload_file_to_drive(
                        file_bytes=file_bytes,
                        filename=filename,
                        category="Assignments",
                        subject=subject,
                        status="Pending"  # no chapter needed for assignments
                    )

                    # ✅ Optionally: store metadata in MongoDB here
                    store_file_metadata(
                        subject=subject,
                        chapter=None,
                        topic=topic,
                        filename=filename,
                        file_id=file_id,
                        drive_link=drive_link,
                        category="Assignments",
                        status="Pending"
                    )

                except Exception as e:
                    await interaction.followup.send(f"❌ File upload failed: {e}", ephemeral=True)
                    return

            # ✅ Create calendar event
            try:
                event_link = create_event(subject, chapter, topic, deadline_iso, description)
            except Exception as e:
                print(f"⚠️ Calendar error: {e}")
                event_link = None

            # ✅ Respond
            reply = f"✅ Assignment set for **{subject} - Chapter {chapter} - {topic}**"
            if event_link:
                reply += f"\n📅 [Calendar Event]({event_link})"
            if drive_link:
                reply += f"\n📎 [File Link]({drive_link})"

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

            # ✅ Upload to Google Drive
            try:
                file_id, drive_link = upload_file_to_drive(
                    file_bytes=file_bytes,
                    filename=filename,
                    category="Notes",  # Later: make user pick this
                    subject=context["subject"],
                    chapter=context["chapter"]
                )
            except Exception as e:
                await message.channel.send(f"❌ Upload failed: {e}")
                return

            # ✅ Store metadata in MongoDB
            try:
                store_file_metadata(
                    subject=context["subject"],
                    chapter=context["chapter"],
                    topic=context["topic"],
                    filename=filename,
                    file_id=file_id,
                    drive_link=drive_link,
                    category="Notes"
                )
            except Exception as e:
                await message.channel.send(f"⚠️ Drive upload success but DB failed: {e}")
                return

            # ✅ Confirm in Discord
            await message.channel.send(
                f"✅ **{filename}** saved under:\n"
                f"> 📚 **Subject**: {context['subject']}\n"
                f"> 📖 **Chapter**: {context['chapter']}\n"
                f"> 🔖 **Topic**: {context['topic']}\n"
                f"> 🔗 [View File]({drive_link})"
            )


client = MyClient()

@client.event
async def on_ready():
    print(f"🤖 Bot online as {client.user}")

client.run(DISCORD_TOKEN)

