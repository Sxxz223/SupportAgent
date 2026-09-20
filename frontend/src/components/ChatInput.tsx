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
  allowImages?: boolean;
};

export function ChatInput({ disabled, onSend, allowImages = true }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageError, setImageError] = useState("");
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
    textarea.style.height = `${value ? Math.min(Math.max(textarea.scrollHeight, 32), 80) : 32}px`;
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
    const file = event.target.files?.[0] ?? null;
    setImageError("");
    if (file && (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024)) {
      setImageError("请选择不超过 10 MB 的 PNG、JPEG 或 WebP 图片。");
      event.target.value = "";
      return;
    }
    setSelectedImage(file);
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
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className={`chat-input ${allowImages ? "" : "chat-input--text"}`} onSubmit={handleSubmit}>
      {imageError && <p className="r-image-error" role="alert">{imageError}</p>}
      {selectedImage && previewUrl && (
        <div className="image-preview">
          <img src={previewUrl} alt="Selected preview" />
          <div>
            <span>{selectedImage.name}</span>
            <button type="button" onClick={removeImage} disabled={disabled}>
              移除图片
            </button>
          </div>
        </div>
      )}
      <label className="sr-only" htmlFor="message-input">
        输入消息
      </label>
      <div className="chat-input__row">
        {allowImages && <input
          ref={fileInputRef}
          className="sr-only"
          id="image-input"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={handleImageChange}
          disabled={disabled}
        />}
        {allowImages && <label className="attach-button" htmlFor="image-input" aria-label="上传图片">
          <span aria-hidden="true">+</span>
        </label>}
        <textarea
          ref={textareaRef}
          id="message-input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述当前情况，或补充你的反馈…"
          maxLength={4000}
          rows={1}
          disabled={disabled}
        />
        <button
          className="send-button"
          type="submit"
          aria-label={disabled ? "请稍候" : "发送消息"}
          disabled={disabled || (value.trim().length === 0 && !selectedImage)}
        >
          <span aria-hidden="true">↑</span>
        </button>
      </div>
    </form>
  );
}
