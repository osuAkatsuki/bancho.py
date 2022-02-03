from discord_slash.utils.manage_commands import create_choice, create_option
profile = [
    create_option(
        name="user",
        description="Select user.",
        option_type=3,
        required=False,
    ),
    create_option(
        name="mode",
        description="Select mode.",
        option_type=3,
        required=False,
        choices=[
            create_choice(name="Standard", value="0"),
            create_choice(name="Taiko", value="1"),
            create_choice(name="Catch", value="2"),
            create_choice(name="Mania", value="3"),
        ]
    ),
    create_option(
        name="mods",
        description="Select mods.",
        option_type=3,
        required=False,
        choices=[
            create_choice(name="Vanilla", value="vn"),
            create_choice(name="Relax", value="rx"),
            create_choice(name="Autopilot", value="ap")
        ]
    ),
    create_option(
        name="size",
        description="Do you want to see all info or only basic",
        option_type=3,
        required=False,
        choices=[
            create_choice(name="Basic", value="basic"),
            create_choice(name="Full", value="full"),
        ]
    ),
]

restrict = [
    create_option(
        name="user",
        description="Specify user by their name.",
        option_type=3,
        required=True,
    ),
    create_option(
        name="reason",
        description="Specify Reason",
        option_type=3,
        required=True,
    ),
]

# silence = [
#     create_option(
#         name="user",
#         description="Specify user by their name.",
#         option_type=3,
#         required=True
#     ),
#     create_option(
#         name="duration",
#         description="Specify duration of silence, by number followed by time unit, e.g. 7d for 7 days.",
#         option_type=3,
#         required=True
#     ),
#     create_option(
#         name="reason",
#         description="Specify reason",
#         option_type=3,
#         required=True
#     ),
# ]

addnote = [
    create_option(
        name="user",
        description="Specify user by their name.",
        option_type=3,
        required=True
    ),
    create_option(
        name="note_content",
        description="Note message, the title is pretty self explainatory",
        option_type=3,
        required=True
    ),
]

checknotes = [
    create_option(
        name="target",
        description="Specify target user by their name.",
        option_type=3,
        required=False
    ),
    create_option(
        name="author",
        description="Specify admin by their name.",
        option_type=3,
        required=False
    ),
    create_option(
        name="page",
        description="Specify page",
        option_type=3,
        required=False
    )
]

scores = [
    create_option(
        name="user",
        description="Specify user by their name. You can omit this if you are discord connected.",
        option_type=3,
        required=False
    ),
    create_option(
        name = "type",
        description = "Specify score type(best/recent).",
        option_type=3,
        required=False,
        choices = [
            create_choice(name="Best", value="best"),
            create_choice(name="Recent", value="recent")
        ]
    ),
    create_option(
        name="mode",
        description="Specify what mode was the score set in. (like osu!std etc.)",
        option_type=3,
        required=False,
        choices = [
            create_choice(name="osu!std Vanilla", value="0"),
            create_choice(name="osu!std Relax", value="4"),
            create_choice(name="osu!std Autopilot", value="7"),
            create_choice(name="osu!catch Vanilla", value="2"),
            create_choice(name="osu!catch Relax", value="6"),
            create_choice(name="osu!taiko Vanilla", value="1"),
            create_choice(name="osu!taiko Relax", value="5"),
            create_choice(name="osu!mania", value="3")
        ]
    ),
    create_option(
        name="mods",
        description="Specify mods you used in the play.",
        option_type=3,
        required=False
    ),
        create_option(
        name="limit",
        description="Specify how many plays you want to display. (max number is 100!!)",
        option_type=3,
        required=False
    )
]