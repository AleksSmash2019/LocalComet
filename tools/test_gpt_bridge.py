from modules.gpt_client import gpt_status, ask_gpt


def main():
    print(gpt_status())
    print()
    print("TEST GPT REQUEST:")
    print(
        ask_gpt(
            "Ответь одной строкой: GPT Bridge для LocalComet работает.",
            max_output_tokens=200,
        )
    )


if __name__ == "__main__":
    main()