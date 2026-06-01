! C04: FORALL construct
program forall_construct
    implicit none
    integer, dimension(5, 5) :: A
    integer :: i, j
    
    ! The construct below will be traced
    FORALL (i=1:5, j=1:5, i == j)
        A(i, j) = 1
    END FORALL
end program forall_construct
