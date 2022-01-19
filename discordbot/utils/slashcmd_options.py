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