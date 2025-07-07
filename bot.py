import discord
from discord import app_commands
from config import DISCORD_TOKEN, GUILD_ID
from mongo_handler import get_notes_by_subject_and_chapter, list_assignments,list_notes
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

        @self.tree.command(guild=guild, name="get_notes", description="View uploaded notes by subject and chapter")
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
        
        
        @self.tree.command(guild=guild, name="list_notes", description="View notes by subject and chapter")
        @app_commands.describe(
            subject="(Optional) Filter by subject",
            chapter="(Optional) Filter by chapter"
        )
        async def list_notes_cmd(interaction: discord.Interaction, subject: str = None, chapter: str = None):
            await interaction.response.defer(ephemeral=True, thinking=True)

            try:
                # Replace this with the actual MongoDB query function once you provide it:
                notes = list_notes(subject=subject, chapter=chapter)

                if not notes:
                    await interaction.followup.send("📂 No notes found for the given criteria.", ephemeral=True)
                    return

                reply = f"📘 **Notes"
                if subject:
                    reply += f" for {subject}"
                if chapter:
                    reply += f" / Chapter {chapter}"
                reply += ":**\n\n"

                for n in notes[:10]:
                    reply += f"• **{n['filename']}** → [Open]({n['drive_link']})\n"

                if len(notes) > 10:
                    reply += f"\n...and {len(notes) - 10} more."

                await interaction.followup.send(reply, ephemeral=True)

            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching notes: {e}", ephemeral=True)

        @self.tree.command(guild=guild, name="set_assignment", description="Set an assignment. Upload files after.")
        @app_commands.describe(
            subject="(Optional) Subject name",
            chapter="(Optional) Chapter number or name",
            topic="(Optional) Topic name",
            deadline="(Optional) Deadline (YYYY-MM-DD)",
            description="(Optional) Assignment description"
        )
        async def set_assignment(
            interaction: discord.Interaction,
            subject: str = None,
            chapter: str = None,
            topic: str = None,
            deadline: str = None,
            description: str = None,
        ):
            await interaction.response.defer(ephemeral=True, thinking=True)
            print("🚀 /set_assignment triggered")

            deadline_iso = None
            if deadline:
                try:
                    deadline_iso = deadline + "T23:59:00"
                    datetime.fromisoformat(deadline_iso)
                except Exception as e:
                    print(f"⚠️ Invalid deadline: {e}")
                    await interaction.followup.send("❌ Invalid deadline format. Use YYYY-MM-DD", ephemeral=True)
                    return

            # Save the context for follow-up file uploads
            user_upload_context[interaction.user.id] = {
                "subject": subject,
                "chapter": chapter,
                "topic": topic,
                "category": "Assignments",
                "status": "Pending",
                "deadline": deadline_iso,
                "description": description
            }

            print(f"📥 Context saved: {user_upload_context[interaction.user.id]}")

            # Try to create event if possible
            event_link = None
            if all([subject, chapter, topic, deadline_iso, description]):
                try:
                    event_link = create_event(subject, chapter, topic, deadline_iso, description)
                except Exception as e:
                    print(f"⚠️ Calendar creation failed: {e}")

            # Respond to user
            reply = "✅ Assignment context set."
            if subject: reply += f"\n📚 Subject: {subject}"
            if chapter: reply += f"\n📖 Chapter: {chapter}"
            if topic: reply += f"\n🔖 Topic: {topic}"
            if deadline: reply += f"\n📅 Deadline: {deadline}"
            if description: reply += f"\n📝 Description: {description}"
            if event_link: reply += f"\n🔗 [Calendar Event]({event_link})"
            reply += "\n\n📥 Now send your file(s) directly as a message to upload them."

            await interaction.followup.send(reply, ephemeral=True)

        @self.tree.command(guild=guild, name="list_assignments", description="View upcoming or pending assignments")
        @app_commands.describe(
            subject="(Optional) Filter by subject",
            status="Assignment status: Pending or Completed"
        )
        async def list_assignments_cmd(interaction: discord.Interaction, subject: str = None, status: str = "Pending"):
            await interaction.response.defer(ephemeral=True, thinking=True)

            try:
                assignments = list_assignments(subject=subject, status=status.capitalize())

                if not assignments:
                    await interaction.followup.send("📭 No assignments found for the given criteria.", ephemeral=True)
                    return

                reply = f"📋 **{status.capitalize()} Assignments"
                if subject:
                    reply += f" for {subject}"
                reply += ":**\n\n"

                for a in assignments[:10]:
                    due = a.get("deadline")
                    due_str = due.strftime("%Y-%m-%d") if due else "N/A"
                    assignment_id = str(a["_id"])[:6]  # Shorten ID for readability

                    reply += (
                        f"• 📌 **ID:** `{assignment_id}`\n"
                        f"  • 📚 **{a.get('subject', 'N/A')}** / {a.get('chapter', 'N/A')} / {a.get('topic', 'N/A')}\n"
                        f"  • 🗓️ Due: {due_str}\n\n"
                    )

                if len(assignments) > 10:
                    reply += f"\n...and {len(assignments) - 10} more."

                await interaction.followup.send(reply, ephemeral=True)

            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching assignments: {e}", ephemeral=True)
    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.attachments:
            return

        user_id = message.author.id
        if user_id not in user_upload_context:
            await message.channel.send("❗ Please use `/upload` or `/set_assignment` before sending a file.")
            return

        context = user_upload_context.pop(user_id)  # Remove after first use

        for attachment in message.attachments:
            try:
                file_bytes = await attachment.read()
                filename = attachment.filename

                # ✅ Use saved context values
                category = context.get("category", "Notes")
                status = context.get("status", "Pending") if category == "Assignments" else None

                # ✅ Upload to Google Drive with correct folder logic
                file_id, drive_link = upload_file_to_drive(
                    file_bytes=file_bytes,
                    filename=filename,
                    category=category,
                    subject=context.get("subject"),
                    chapter=context.get("chapter"),
                    status=status
                )

                # ✅ Store metadata in MongoDB
                store_file_metadata(
                    subject=context.get("subject"),
                    chapter=context.get("chapter"),
                    topic=context.get("topic"),
                    filename=filename,
                    file_id=file_id,
                    drive_link=drive_link,
                    category=category,
                    status=status
                )

                # ✅ Confirm upload in Discord
                await message.channel.send(
                    f"✅ **{filename}** saved under:\n"
                    f"> 📁 **Category**: {category}\n"
                    f"> 📚 **Subject**: {context.get('subject')}\n"
                    f"> 📖 **Chapter**: {context.get('chapter')}\n"
                    f"> 🔖 **Topic**: {context.get('topic')}\n"
                    f"> 🔗 [View File]({drive_link})"
                )

            except Exception as e:
                await message.channel.send(f"❌ Upload failed: {e}")

client = MyClient()

@client.event
async def on_ready():
    await client.tree.sync(guild=discord.Object(id=GUILD_ID))  # 🔁 Force re-sync
    print(f"🤖 Bot online as {client.user} and commands synced to guild {GUILD_ID}")

client.run(DISCORD_TOKEN)
