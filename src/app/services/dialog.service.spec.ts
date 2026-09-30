import { DialogService } from './dialog.service';

describe('DialogService', () => {
  it('resolves confirm() with true when OK is chosen', async () => {
    const dialog = new DialogService();
    const result = dialog.confirm('Warning', 'Are you sure you want to delete this student?');
    expect(dialog.state()?.kind).toBe('confirm');
    dialog.close(true);
    expect(await result).toBe(true);
    expect(dialog.state()).toBeNull();
  });

  it('resolves confirm() with false when cancelled', async () => {
    const dialog = new DialogService();
    const result = dialog.confirm('Warning', 'msg');
    dialog.close(false);
    expect(await result).toBe(false);
  });

  it('resolves a pending confirm() with false when another dialog replaces it', async () => {
    const dialog = new DialogService();
    const result = dialog.confirm('Warning', 'msg');
    dialog.success('Deleted!', 'done');
    expect(await result).toBe(false);
    expect(dialog.state()?.kind).toBe('success');
  });

  it('keeps notices open until closed', () => {
    vi.useFakeTimers();
    const dialog = new DialogService();
    dialog.success('Success!', 'done');
    vi.advanceTimersByTime(60_000);
    expect(dialog.state()?.kind).toBe('success');
    dialog.close();
    expect(dialog.state()).toBeNull();
    vi.useRealTimers();
  });
});
