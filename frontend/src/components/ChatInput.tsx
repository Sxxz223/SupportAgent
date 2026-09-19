import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";

type ChatInputProps = {
  disabled: boolean;
  onSend: (message: string, image: File | null) => void;
};

export function ChatInput({ disabled, onSend }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!selectedImage) {
      setPreviewUrl(null);
      return;
    }

    const url = URL.createObjectURL(selectedImage);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedImage]);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`;
  }, [value]);

  function submit() {
    const message = value.trim();
    if ((!message && !selectedImage) || disabled) return;
    const image = selectedImage;
    setValue("");
    setSelectedImage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    onSend(message, image);
  }

  function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedImage(event.target.files?.[0] ?? null);
  }

  function removeImage() {
    setSelectedImage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      {selectedImage && previewUrl && (
        <div className="image-preview">
          <img src={previewUrl} alt="Selected preview" />
          <div>
            <span>{selectedImage.name}</span>
            <button type="button" onClick={removeImage} disabled={disabled}>
              Remove image
            </button>
          </div>
        </div>
      )}
      <label className="sr-only" htmlFor="message-input">
        Message
      </label>
      <div className="chat-input__row">
        <input
          ref={fileInputRef}
          className="sr-only"
          id="image-input"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={handleImageChange}
          disabled={disabled}
        />
        <label className="attach-button" htmlFor="image-input" aria-label="Attach image">
          <span aria-hidden="true">+</span>
        </label>
        <textarea
          ref={textareaRef}
          id="message-input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message…"
          rows={1}
          disabled={disabled}
        />
        <button
          className="send-button"
          type="submit"
          aria-label={disabled ? "Please wait" : "Send"}
          disabled={disabled || (value.trim().length === 0 && !selectedImage)}
        >
          <span aria-hidden="true">↑</span>
        </button>
      </div>
    </form>
  );
}
